"""FlowBoxChild tiles for the grid view."""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf, Pango

from enhancement import Enhancement
from imaging import load_thumbnail_async, get_category_icon
from constants import CATEGORY_MAP

TILE_SIZE = 170
THUMB_SIZE = 48


class EnhancementTile(Gtk.FlowBoxChild):
    def __init__(self, enhancement: Enhancement):
        super().__init__()
        self.enhancement = enhancement
        self._build()

    def _build(self):
        overlay = Gtk.Overlay()
        self.add(overlay)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(6)
        box.set_margin_end(6)
        box.set_size_request(TILE_SIZE, -1)
        overlay.add(box)

        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.pack_start(top_row, False, False, 0)

        self._thumb_image = Gtk.Image()
        self._thumb_image.set_size_request(THUMB_SIZE, THUMB_SIZE)
        top_row.pack_start(self._thumb_image, False, False, 0)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        top_row.pack_start(info_box, True, True, 0)

        name_label = Gtk.Label(label=self.enhancement.name)
        name_label.set_xalign(0)
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_label.set_max_width_chars(14)
        name_label.set_line_wrap(False)
        ctx = name_label.get_style_context()
        ctx.add_class("tile-name")
        info_box.pack_start(name_label, False, False, 0)

        if self.enhancement.summary:
            summary = Gtk.Label(label=self.enhancement.summary[:40])
            summary.set_xalign(0)
            summary.set_ellipsize(Pango.EllipsizeMode.END)
            summary.set_max_width_chars(14)
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

        badge_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        badge_box.set_halign(Gtk.Align.END)
        badge_box.set_valign(Gtk.Align.START)
        badge_box.set_margin_top(4)
        badge_box.set_margin_end(4)
        if self.enhancement.installed:
            badge = Gtk.Label(label="Installed")
            badge.get_style_context().add_class("installed-badge")
            badge_box.pack_start(badge, False, False, 0)
        if badge_box.get_children():
            overlay.add_overlay(badge_box)

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
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_size_request(100, 70)
        box.set_halign(Gtk.Align.CENTER)

        icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.DND)
        icon.set_pixel_size(28)
        box.pack_start(icon, False, False, 0)

        name = Gtk.Label(label=label)
        name.set_line_wrap(True)
        name.set_justify(Gtk.Justification.CENTER)
        name.set_max_width_chars(14)
        ctx = name.get_style_context()
        ctx.add_class("tile-name")
        box.pack_start(name, False, False, 0)

        count_label = Gtk.Label(label=f"{count}" if count > 0 else "")
        count_label.get_style_context().add_class("dim-label")
        box.pack_start(count_label, False, False, 0)

        self.add(box)
        self.show_all()
