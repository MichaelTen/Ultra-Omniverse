extends Control

var cfg: ConfigFile = ConfigFile.new()

func _ready() -> void:
	var err: int = cfg.load("res://ui_mock.cfg")
	if err != OK:
		push_error("Failed to load config file")
	_build_layout()


func _build_layout() -> void:
	# Read config (typed)
	var pad: int = int(cfg.get_value("window", "content_padding", 16))
	var gutter: int = int(cfg.get_value("layout", "gutter", 8))
	var has_header: bool = bool(cfg.get_value("layout", "has_header", true))
	var has_sidebar: bool = bool(cfg.get_value("layout", "has_sidebar", true))
	var has_status: bool = bool(cfg.get_value("layout", "has_statusbar", true))
	var header_h: int = int(cfg.get_value("layout", "header_height", 48))
	var status_h: int = int(cfg.get_value("layout", "statusbar_height", 28))
	var sidebar_frac: float = float(cfg.get_value("layout", "sidebar_width", 0.22))

	# Colors (typed)
	var col_bg0: Color = Color(str(cfg.get_value("theme", "bg0", "#1d2021")))
	var col_bg1: Color = Color(str(cfg.get_value("theme", "bg1", "#282828")))
	var col_bar: Color = Color(str(cfg.get_value("theme", "border", "#3c3836")))
	var col_side: Color = Color("#504945")
	var col_fg: Color = Color(str(cfg.get_value("theme", "fg", "#ebdbb2")))

	# Background
	var bg_rect: ColorRect = ColorRect.new()
	bg_rect.color = col_bg0
	bg_rect.anchor_right = 1.0
	bg_rect.anchor_bottom = 1.0
	add_child(bg_rect)

	# Root container that provides padding and vertical stacking
	var root: VBoxContainer = VBoxContainer.new()
	root.anchor_right = 1.0
	root.anchor_bottom = 1.0
	root.offset_left = pad
	root.offset_top = pad
	root.offset_right = -pad
	root.offset_bottom = -pad
	root.add_theme_constant_override("separation", gutter)
	add_child(root)

	# Header
	if has_header:
		var header: ColorRect = ColorRect.new()
		header.color = col_bar
		header.custom_minimum_size = Vector2(0, header_h)
		root.add_child(header)

		var hlabel: Label = Label.new()
		hlabel.text = str(cfg.get_value("header", "title", "Ultra Omniverse"))
		hlabel.self_modulate = col_fg
		hlabel.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		hlabel.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		hlabel.anchor_right = 1.0
		hlabel.anchor_bottom = 1.0
		header.add_child(hlabel)

	# Middle row that expands
	var content: HBoxContainer = HBoxContainer.new()
	content.add_theme_constant_override("separation", gutter)
	content.size_flags_vertical = Control.SIZE_EXPAND_FILL
	root.add_child(content)

	# Sidebar
	if has_sidebar:
		var sidebar: ColorRect = ColorRect.new()
		sidebar.color = col_side
		var viewport_w: float = float(get_viewport_rect().size.x)
		var sidebar_px: int = int(round(viewport_w * sidebar_frac))
		sidebar.custom_minimum_size = Vector2(sidebar_px, 0)
		sidebar.size_flags_vertical = Control.SIZE_EXPAND_FILL
		content.add_child(sidebar)

		var slabel: Label = Label.new()
		slabel.text = "Sidebar"
		slabel.self_modulate = col_fg
		slabel.anchor_right = 1.0
		slabel.anchor_bottom = 1.0
		slabel.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		slabel.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		sidebar.add_child(slabel)

	# Main area
	var main_area: ColorRect = ColorRect.new()
	main_area.color = col_bg1
	main_area.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	main_area.size_flags_vertical = Control.SIZE_EXPAND_FILL
	content.add_child(main_area)

	var mlabel: Label = Label.new()
	mlabel.text = "Main"
	mlabel.self_modulate = col_fg
	mlabel.anchor_right = 1.0
	mlabel.anchor_bottom = 1.0
	mlabel.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	mlabel.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	main_area.add_child(mlabel)

	# Status bar
	if has_status:
		var status: ColorRect = ColorRect.new()
		status.color = col_bar
		status.custom_minimum_size = Vector2(0, status_h)
		root.add_child(status)

		var stlabel: Label = Label.new()
		stlabel.text = "Status: Ready"
		stlabel.self_modulate = col_fg
		stlabel.anchor_right = 1.0
		stlabel.anchor_bottom = 1.0
		stlabel.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		stlabel.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		status.add_child(stlabel)
