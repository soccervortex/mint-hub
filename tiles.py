"""FlowBoxChild tiles for the grid view."""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf, Pango

from enhancement import Enhancement
from imaging import load_thumbnail_async, get_category_icon
from constants import CATEGORY_MAP

TILE_SIZE = 220
THUMB_SIZE = 96


class EnhancementTile(Gtk.FlowBoxChild):
    def __init__(self, enhancement: Enhancement):
        super().__init__()
        self.enhancement = enhancement
        self._build()

    def _build(self):
        overlay = Gtk.Overlay()
        self.add(overlay)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_size_request(TILE_SIZE, -1)
        overlay.add(box)

        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.pack_start(top_row, False, False, 0)

        self._thumb_image = Gtk.Image()
        self._thumb_image.set_size_request(THUMB_SIZE, THUMB_SIZE)
        top_row.pack_start(self._thumb_image, False, False, 0)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        top_row.pack_start(info_box, True, True, 0)

        name_label = Gtk.Label(label=self.enhancement.name)
        name_label.set_xalign(0)
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_label.set_max_width_chars(18)
        name_label.set_line_wrap(False)
        ctx = name_label.get_style_context()
        ctx.add_class("tile-name")
        info_box.pack_start(name_label, False, False, 0)

        if self.enhancement.summary:
            summary = Gtk.Label(label=self.enhancement.summary[:60])
            summary.set_xalign(0)
            summary.set_ellipsize(Pango.EllipsizeMode.END)
            summary.set_max_width_chars(18)
            ctx = summary.get_style_context()
            ctx.add_class("dim-label")
            info_box.pack_start(summary, False, False, 0)

        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        box.pack_start(bottom, False, False, 0)

        cat_info = CATEGORY_MAP.get(self.enhancement.category, {})
        cat_icon_name = cat_info.get("icon", "application-x-addon")
        cat_label_text = cat_info.get("label", self.enhancement.category)

        cat_icon = Gtk.Image.new_from_icon_name(cat_icon_name, Gtk.IconSize.SMALL_TOOLBAR)
        bottom.pack_start(cat_icon, False, False, 0)

        cat_label = Gtk.Label(label=cat_label_text)
        cat_label.get_style_context().add_class("dim-label")
        cat_label.set_ellipsize(Pango.EllipsizeMode.END)
        bottom.pack_start(cat_label, False, False, 0)

        spacer = Gtk.Label()
        bottom.pack_start(spacer, True, True, 0)

        if self.enhancement.avg_rating > 0:
            star = Gtk.Image.new_from_icon_name("starred-symbolic", Gtk.IconSize.SMALL_TOOLBAR)
            bottom.pack_end(star, False, False, 0)
            rating_label = Gtk.Label(label=f"{self.enhancement.avg_rating:.1f}")
            rating_label.get_style_context().add_class("dim-label")
            bottom.pack_end(rating_label, False, False, 0)

        if self.enhancement.installed:
            installed_icon = Gtk.Image.new_from_icon_name("object-select-symbolic", Gtk.IconSize.SMALL_TOOLBAR)
            installed_box = Gtk.Box()
            installed_box.set_halign(Gtk.Align.END)
            installed_box.set_valign(Gtk.Align.START)
            installed_box.set_margin_top(4)
            installed_box.set_margin_end(4)
            installed_box.pack_start(installed_icon, False, False, 0)
            overlay.add_overlay(installed_box)

        source = self.enhancement.thumbnail_local or self.enhancement.thumbnail_url
        category_icon = cat_info.get("icon", "application-x-addon")
        load_thumbnail_async(source, THUMB_SIZE, self._on_thumb_loaded, category_icon)

        self.show_all()

    def _on_thumb_loaded(self, pixbuf):
        if pixbuf:
            self._thumb_image.set_from_pixbuf(pixbuf)

    def refresh_state(self):
        pass


class CategoryTile(Gtk.FlowBoxChild):
    def __init__(self, cat_id: str, label: str, icon_name: str, count: int = 0):
        super().__init__()
        self.cat_id = cat_id
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_size_request(120, 80)

        icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.DIALOG)
        box.pack_start(icon, False, False, 0)

        name = Gtk.Label(label=label)
        name.set_line_wrap(True)
        name.set_justify(Gtk.Justification.CENTER)
        box.pack_start(name, False, False, 0)

        if count > 0:
            count_label = Gtk.Label(label=f"{count} items")
            count_label.get_style_context().add_class("dim-label")
            box.pack_start(count_label, False, False, 0)

        self.add(box)
        self.show_all()
