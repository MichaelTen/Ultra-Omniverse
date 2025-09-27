#!/usr/bin/env python3
"""Generate a procedural 2D planet billboard with biomes, rivers, and city lights."""

import argparse
import math
import secrets
from dataclasses import dataclass
from typing import Tuple

import numpy as np
from PIL import Image


@dataclass
class PlanetMaps:
    elevation: np.ndarray
    moisture: np.ndarray
    temperature: np.ndarray
    rivers: np.ndarray
    cities: np.ndarray
    mask: np.ndarray
    distance: np.ndarray
    radius: float


class PlanetGenerator:
    def __init__(self, width: int, height: int, seed: int) -> None:
        self.width = width
        self.height = height
        self.seed = int(seed)
        self.rng = np.random.default_rng(self.seed)

    @staticmethod
    def _fade(t: np.ndarray) -> np.ndarray:
        return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)

    def _value_noise(self, shape: Tuple[int, int], res: Tuple[int, int], rng: np.random.Generator) -> np.ndarray:
        h, w = shape
        ry = max(1, int(res[0]))
        rx = max(1, int(res[1]))
        grid = rng.random((ry + 1, rx + 1), dtype=np.float32)

        y = np.linspace(0.0, float(ry), h, endpoint=False, dtype=np.float32)
        x = np.linspace(0.0, float(rx), w, endpoint=False, dtype=np.float32)

        y0 = np.floor(y).astype(int)
        x0 = np.floor(x).astype(int)
        y1 = np.minimum(y0 + 1, ry)
        x1 = np.minimum(x0 + 1, rx)

        fy = y - y0
        fx = x - x0
        sy = self._fade(fy)[:, None]
        sx = self._fade(fx)[None, :]

        g00 = grid[y0[:, None], x0[None, :]]
        g10 = grid[y1[:, None], x0[None, :]]
        g01 = grid[y0[:, None], x1[None, :]]
        g11 = grid[y1[:, None], x1[None, :]]

        n0 = g00 * (1.0 - sx) + g01 * sx
        n1 = g10 * (1.0 - sx) + g11 * sx
        return (n0 * (1.0 - sy) + n1 * sy).astype(np.float32)

    def _fractal_noise(self, shape: Tuple[int, int], res: Tuple[int, int], octaves: int, persistence: float,
                       lacunarity: float, seed_offset: int = 0) -> np.ndarray:
        noise = np.zeros(shape, dtype=np.float32)
        amplitude = 1.0
        frequency = 1.0
        total_amplitude = 0.0
        for octave in range(octaves):
            scaled_res = (
                max(1, int(res[0] * frequency)),
                max(1, int(res[1] * frequency)),
            )
            octave_seed = self.seed + seed_offset + octave * 31
            octave_rng = np.random.default_rng(octave_seed)
            noise += self._value_noise(shape, scaled_res, octave_rng) * amplitude
            total_amplitude += amplitude
            amplitude *= persistence
            frequency *= lacunarity
        if total_amplitude > 0:
            noise /= total_amplitude
        return noise

    def _trace_rivers(self, elevation: np.ndarray, moisture: np.ndarray, mask: np.ndarray,
                      sea_level: float = 0.0) -> np.ndarray:
        h, w = elevation.shape
        river_map = np.zeros_like(elevation, dtype=np.float32)
        candidates = np.argwhere(mask & (elevation > sea_level + 0.05) & (moisture > 0.45))
        if candidates.size == 0:
            return river_map
        self.rng.shuffle(candidates)
        river_budget = max(6, (h * w) // 22000)
        neighbors = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
        for start_y, start_x in candidates[:river_budget]:
            y, x = int(start_y), int(start_x)
            visited = set()
            for _ in range(800):
                if (y, x) in visited:
                    break
                visited.add((y, x))
                river_map[y, x] += 1.0
                if elevation[y, x] <= sea_level:
                    break
                best_pos = None
                best_score = elevation[y, x]
                for dy, dx in neighbors:
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx]:
                        score = elevation[ny, nx] - 0.015 * moisture[ny, nx]
                        if score < best_score - 1e-4:
                            best_score = score
                            best_pos = (ny, nx)
                if best_pos is None:
                    break
                y, x = best_pos
        if river_map.max() > 0:
            river_map /= river_map.max()
            for _ in range(2):
                river_map = (
                    river_map +
                    0.35 * (np.roll(river_map, 1, axis=0) + np.roll(river_map, -1, axis=0) +
                            np.roll(river_map, 1, axis=1) + np.roll(river_map, -1, axis=1))
                ) / 2.4
        return np.clip(river_map, 0.0, 1.0)

    def _generate_cities(self, elevation: np.ndarray, moisture: np.ndarray, temperature: np.ndarray,
                         mask: np.ndarray, sea_level: float = 0.0) -> np.ndarray:
        suitability = mask & (elevation > sea_level + 0.02) & (elevation < 0.6)
        suitability &= (temperature > 0.18) & (temperature < 0.85)
        suitability &= (moisture > 0.18) & (moisture < 0.85)

        density_noise = self._fractal_noise(elevation.shape, (14, 14), 4, 0.55, 2.1, 1001)
        river_influence = np.clip(self._fractal_noise(elevation.shape, (28, 28), 3, 0.5, 2.3, 1107) - 0.4, 0, 1)

        cities = np.zeros_like(elevation, dtype=np.float32)
        base_density = np.clip((density_noise - 0.55) * 4.5, 0.0, 1.0)
        cities[suitability] = base_density[suitability]
        cities *= 0.65 + 0.35 * river_influence
        return np.clip(cities ** 1.6, 0.0, 1.0)

    @staticmethod
    def _compute_normals(height_map: np.ndarray, mask: np.ndarray) -> np.ndarray:
        gy, gx = np.gradient(height_map)
        normal = np.dstack((-gx, -gy, np.ones_like(height_map)))
        norm = np.linalg.norm(normal, axis=2, keepdims=True)
        normal /= np.clip(norm, 1e-6, None)
        normal[~mask] = np.array([0.0, 0.0, 1.0], dtype=np.float32)
        return normal

    @staticmethod
    def _lerp(a: np.ndarray, b: np.ndarray, t: np.ndarray) -> np.ndarray:
        return a + (b - a) * t[..., None]

    def generate_maps(self) -> PlanetMaps:
        shape = (self.height, self.width)
        yy, xx = np.indices(shape, dtype=np.float32)
        cx = self.width / 2.0
        cy = self.height / 2.0
        radius = min(cx, cy) * 0.95
        distance = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2, dtype=np.float32)
        mask = distance <= radius

        base = self._fractal_noise(shape, (4, 4), 6, 0.5, 2.1, 0)
        mountains = self._fractal_noise(shape, (8, 8), 5, 0.5, 2.0, 57)
        ridges = self._fractal_noise(shape, (24, 24), 4, 0.45, 2.0, 113)
        ridge_peaks = 1.0 - np.abs(ridges * 2.0 - 1.0)

        elevation = base * 0.55 + mountains * 0.35 + ridge_peaks * 0.25
        elevation = (elevation - elevation.mean()) / (elevation.std() + 1e-5)
        elevation *= 0.45
        falloff = np.clip(1.0 - (distance / radius) ** 6, 0.0, 1.0)
        elevation = elevation * falloff - (1.0 - falloff) * 0.65
        elevation = np.clip(elevation, -1.3, 1.1)

        moisture = self._fractal_noise(shape, (6, 6), 5, 0.58, 2.05, 201)
        moisture += (self._fractal_noise(shape, (18, 18), 3, 0.6, 2.2, 301) - 0.5) * 0.3
        moisture += np.clip(-elevation, 0.0, 1.0) * 0.15
        moisture = np.clip(moisture, 0.0, 1.0)

        latitude = np.abs((yy - cy) / radius)
        temperature = 1.0 - latitude ** 1.55
        temperature -= np.clip(elevation, 0.0, None) * 0.55
        temperature += (self._fractal_noise(shape, (10, 10), 4, 0.52, 2.05, 419) - 0.5) * 0.25
        temperature = np.clip(temperature, 0.0, 1.0)

        rivers = self._trace_rivers(elevation, moisture, mask)
        cities = self._generate_cities(elevation, moisture, temperature, mask)

        return PlanetMaps(
            elevation=elevation,
            moisture=moisture,
            temperature=temperature,
            rivers=rivers,
            cities=cities,
            mask=mask,
            distance=distance,
            radius=radius,
        )

    def render(self, maps: PlanetMaps) -> Image.Image:
        sea_level = 0.0
        h, w = maps.elevation.shape
        color = np.zeros((h, w, 3), dtype=np.float32)
        space_color = np.array([3, 7, 18], dtype=np.float32) / 255.0
        result = np.tile(space_color, (h, w, 1))

        ocean_mask = (maps.elevation <= sea_level) & maps.mask
        land_mask = (~ocean_mask) & maps.mask

        depth = np.clip((sea_level - maps.elevation) / 1.5, 0.0, 1.0)
        deep = np.array([5, 34, 92], dtype=np.float32) / 255.0
        shallow = np.array([24, 105, 164], dtype=np.float32) / 255.0
        ocean_color = self._lerp(deep, shallow, depth)
        color[ocean_mask] = ocean_color[ocean_mask]

        base_land = np.array([108, 130, 92], dtype=np.float32) / 255.0
        color[land_mask] = base_land

        moisture = maps.moisture
        temperature = maps.temperature
        elevation = maps.elevation

        desert_mask = land_mask & (moisture < 0.25) & (temperature > 0.45)
        color[desert_mask] = np.array([201, 179, 101], dtype=np.float32) / 255.0

        shrub_mask = land_mask & (moisture < 0.4) & ~desert_mask
        color[shrub_mask] = np.array([166, 148, 102], dtype=np.float32) / 255.0

        forest_mask = land_mask & (moisture > 0.68) & (temperature > 0.3)
        color[forest_mask] = np.array([36, 94, 58], dtype=np.float32) / 255.0

        jungle_mask = land_mask & (moisture > 0.78) & (temperature > 0.55)
        color[jungle_mask] = np.array([28, 82, 44], dtype=np.float32) / 255.0

        grass_mask = land_mask & (moisture > 0.45) & ~forest_mask & ~jungle_mask
        color[grass_mask] = np.array([92, 136, 76], dtype=np.float32) / 255.0

        taiga_mask = land_mask & (temperature < 0.35) & (moisture > 0.35)
        color[taiga_mask] = np.array([70, 102, 74], dtype=np.float32) / 255.0

        mountain_mask = land_mask & (elevation > 0.52)
        color[mountain_mask] = np.array([140, 132, 124], dtype=np.float32) / 255.0

        snow_mask = land_mask & ((temperature < 0.22) | (elevation > 0.68))
        color[snow_mask] = np.array([235, 243, 250], dtype=np.float32) / 255.0

        river_strength = np.clip(maps.rivers, 0.0, 1.0)[..., None]
        if np.any(river_strength > 0):
            river_color = np.array([54, 129, 196], dtype=np.float32) / 255.0
            color = color * (1.0 - river_strength * 0.75) + river_color * river_strength * 0.75

        normals = self._compute_normals(elevation, maps.mask)
        light_dir = np.array([0.45, -0.3, 0.84], dtype=np.float32)
        light_dir /= np.linalg.norm(light_dir)
        light = np.clip(np.sum(normals * light_dir, axis=2), -1.0, 1.0)
        day_light = np.clip(light, 0.0, 1.0)
        night_light = np.clip(-light, 0.0, 1.0)

        shaded = np.zeros_like(color)
        shaded += color * (0.35 + 0.65 * day_light[..., None])
        shaded += color * (0.08 * night_light[..., None])

        if np.any(ocean_mask):
            specular = (day_light ** 8) * 0.45
            shaded[ocean_mask] += specular[ocean_mask, None]

        city_color = np.array([255, 202, 92], dtype=np.float32) / 255.0
        city_glow = maps.cities * night_light
        shaded += city_color * city_glow[..., None] * 1.1

        edge_width = maps.radius * 0.06
        atmosphere_strength = np.clip((maps.radius + edge_width - maps.distance) / edge_width, 0.0, 1.0)
        atmosphere_strength = atmosphere_strength ** 1.5
        atmosphere_color = np.array([72, 124, 255], dtype=np.float32) / 255.0
        shaded += atmosphere_color * atmosphere_strength[..., None] * 0.18

        result[maps.mask] = np.clip(shaded[maps.mask], 0.0, 1.0)

        glow_mask = (~maps.mask) & (maps.distance <= maps.radius + edge_width)
        if np.any(glow_mask):
            glow_strength = np.clip(1.0 - (maps.distance[glow_mask] - maps.radius) / edge_width, 0.0, 1.0) ** 2
            result[glow_mask] = (
                result[glow_mask] * (1.0 - glow_strength[:, None] * 0.6) +
                atmosphere_color * glow_strength[:, None] * 0.6
            )

        result = np.clip(result, 0.0, 1.0)
        image = Image.fromarray((result * 255).astype(np.uint8), mode="RGB")
        return image

    def generate(self) -> Image.Image:
        maps = self.generate_maps()
        return self.render(maps)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a procedural 2D planet billboard with rivers, biomes, and city lights."
    )
    parser.add_argument("--width", type=int, default=1024, help="Planet image width in pixels (default: 1024)")
    parser.add_argument("--height", type=int, default=1024, help="Planet image height in pixels (default: 1024)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument("--output", type=str, default="planet.png", help="Output image file (png or jpg)")
    parser.add_argument("--preview", action="store_true", help="Open the generated image after saving")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.width <= 0 or args.height <= 0:
        raise ValueError("Width and height must be positive integers")
    seed = args.seed if args.seed is not None else secrets.randbelow(2**32)
    generator = PlanetGenerator(args.width, args.height, seed)
    image = generator.generate()
    image.save(args.output)
    print(f"Generated planet saved to {args.output} (seed={seed})")
    if args.preview:
        image.show()


if __name__ == "__main__":
    main()
