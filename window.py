"""Main application window with all pages."""

import logging
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("XApp", "1.0")
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf, Pango, XApp

log = logging.getLogger("minthub")

from constants import CATEGORIES, CATEGORY_MAP, APP_VERSION
from enhancement import Enhancement
from tiles import EnhancementTile, CategoryTile
from imaging import load_thumbnail_async
from packager import create_package, validate_manifest, generate_manifest_template
from safety_scanner import scan_for_upload
from updater import check_for_update, download_and_install

PAGE_ONBOARDING = "onboarding"
PAGE_LOADING = "loading"
PAGE_HOME = "home"
PAGE_BROWSE = "browse"
PAGE_DETAILS = "details"
PAGE_LIBRARY = "library"
PAGE_UPLOAD = "upload"
PAGE_SETTINGS = "settings"


class MainWindow:
    def __init__(self, app):
        self.app = app
        self._search_timeout = None
        self._current_category = None
        self._current_sort = "score"
        self._tile_batch = []
        self._tile_batch_idx = 0
        self._history = []
        self._detail_enh = None
        self._pending_update = None

    def build(self) -> Gtk.ApplicationWindow:
        self.window = Gtk.ApplicationWindow(application=self.app, title="Linux Mint Hub")
        self.window.set_default_size(1100, 750)
        self.window.set_position(Gtk.WindowPosition.CENTER)

        icon_path = Path(__file__).parent / "data" / "mint-hub.svg"
        if icon_path.exists():
            self.window.set_icon_from_file(str(icon_path))

        self._load_css()

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.window.add(main_box)

        self._build_headerbar()
        self.window.set_titlebar(self.headerbar)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(200)
        main_box.pack_start(self.stack, True, True, 0)

        self._build_onboarding_page()
        self._build_loading_page()
        self._build_home_page()
        self._build_browse_page()
        self._build_details_page()
        self._build_library_page()
        self._build_upload_page()
        self._build_settings_page()

        self.progress_revealer = Gtk.Revealer()
        self.progress_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_show_text(True)
        self.progress_revealer.add(self.progress_bar)
        main_box.pack_end(self.progress_revealer, False, False, 0)

        self.toast_revealer = Gtk.Revealer()
        self.toast_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        self.toast_revealer.set_transition_duration(300)
        self.toast_label = Gtk.Label()
        self.toast_label.get_style_context().add_class("toast-bar")
        self.toast_revealer.add(self.toast_label)
        main_box.pack_end(self.toast_revealer, False, False, 0)
        self._toast_timeout = None

        self.window.connect("key-press-event", self._on_key_press)

        self.window.show_all()
        return self.window

    def _load_css(self):
        css = b"""
        .tile-name { font-weight: bold; font-size: 13px; }
        .dim-label { opacity: 0.55; font-size: 11px; }
        .heading { font-size: 20px; font-weight: bold; }
        .subheading { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
        .detail-title { font-size: 24px; font-weight: bold; }
        .detail-author { font-size: 13px; opacity: 0.7; }
        .detail-meta-key { font-weight: 600; opacity: 0.6; font-size: 12px; }
        .detail-meta-val { font-size: 12px; }

        .category-sidebar {
            background: alpha(@theme_fg_color, 0.02);
        }
        .category-sidebar row {
            padding: 10px 14px;
            border-left: 3px solid transparent;
            transition: all 150ms ease;
        }
        .category-sidebar row:selected {
            background-color: alpha(#6BC86B, 0.12);
            border-left-color: #6BC86B;
        }
        .category-sidebar row:hover:not(:selected) {
            background-color: alpha(@theme_fg_color, 0.04);
        }

        flowboxchild {
            border: 1px solid alpha(@theme_fg_color, 0.08);
            border-radius: 8px;
            margin: 2px;
            padding: 1px;
            transition: all 200ms ease;
            background: alpha(@theme_fg_color, 0.015);
        }
        flowboxchild:hover {
            border-color: alpha(#6BC86B, 0.5);
            background: alpha(#6BC86B, 0.06);
        }
        flowboxchild:selected {
            border-color: #6BC86B;
            background: alpha(#6BC86B, 0.08);
        }

        .welcome-title { font-size: 22px; font-weight: bold; }
        .welcome-subtitle { font-size: 13px; opacity: 0.65; }
        .stat-value { font-size: 22px; font-weight: bold; color: #6BC86B; }
        .stat-label { font-size: 10px; opacity: 0.55; }
        .stat-card {
            border: 1px solid alpha(@theme_fg_color, 0.08);
            border-radius: 10px;
            padding: 10px 16px;
            background: alpha(@theme_fg_color, 0.02);
        }
        .section-title { font-size: 16px; font-weight: 600; margin-top: 8px; }
        .cat-count {
            font-size: 10px;
            opacity: 0.4;
            font-weight: 600;
        }

        .toast-bar {
            background: alpha(@theme_fg_color, 0.88);
            color: @theme_bg_color;
            padding: 10px 20px;
            border-radius: 8px;
            margin: 8px 24px;
            font-weight: 500;
        }
        .toast-success { background: #43A047; color: white; }
        .toast-error { background: #E53935; color: white; }

        .featured-tile {
            background: alpha(#6BC86B, 0.06);
            border: 1px solid alpha(#6BC86B, 0.25);
            border-radius: 10px;
            padding: 8px;
        }
        .empty-state {
            opacity: 0.4;
            font-size: 14px;
        }

        .installed-badge {
            background: #43A047;
            color: white;
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 10px;
            font-weight: 600;
        }
        .source-badge {
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 10px;
            font-weight: 600;
        }
        .source-spices {
            background: alpha(#FF9800, 0.15);
            color: #FF9800;
        }
        .source-local {
            background: alpha(#2196F3, 0.15);
            color: #2196F3;
        }

        .update-banner {
            background: alpha(#6BC86B, 0.1);
            border: 1px solid alpha(#6BC86B, 0.3);
            border-radius: 8px;
            padding: 12px 16px;
        }

        button.suggested-action {
            background-color: #6BC86B;
            color: white;
        }
        button.suggested-action:hover {
            background-color: #5BB85B;
        }

        progressbar trough {
            min-height: 6px;
            border-radius: 3px;
        }
        progressbar progress {
            min-height: 6px;
            border-radius: 3px;
            background: #6BC86B;
        }

        frame {
            border-radius: 8px;
        }
        frame > label {
            font-weight: 600;
            opacity: 0.8;
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _build_headerbar(self):
        self.headerbar = Gtk.HeaderBar()
        self.headerbar.set_show_close_button(True)
        self.headerbar.set_title("Linux Mint Hub")
        self.headerbar.set_subtitle("Enhancement Hub for Linux Mint")

        self.back_btn = Gtk.Button.new_from_icon_name("go-previous-symbolic", Gtk.IconSize.BUTTON)
        self.back_btn.connect("clicked", self._on_back)
        self.back_btn.set_visible(False)
        self.back_btn.set_no_show_all(True)
        self.headerbar.pack_start(self.back_btn)

        home_btn = Gtk.Button.new_from_icon_name("go-home-symbolic", Gtk.IconSize.BUTTON)
        home_btn.set_tooltip_text("Home")
        home_btn.connect("clicked", lambda w: self.navigate_to(PAGE_HOME))
        self.headerbar.pack_start(home_btn)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search enhancements...")
        self.search_entry.set_size_request(250, -1)
        self.search_entry.connect("search-changed", self._on_search_changed)
        self.headerbar.pack_start(self.search_entry)

        menu_btn = Gtk.MenuButton()
        menu_btn.set_image(Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.BUTTON))
        menu = Gtk.Menu()
        for label, handler in [
            ("My Library", lambda w: self.navigate_to(PAGE_LIBRARY)),
            ("Upload Enhancement", lambda w: self.navigate_to(PAGE_UPLOAD)),
            ("Settings", lambda w: self.navigate_to(PAGE_SETTINGS)),
            ("Refresh Catalog", lambda w: self.app.refresh_catalog()),
        ]:
            item = Gtk.MenuItem(label=label)
            item.connect("activate", handler)
            menu.append(item)
        menu.show_all()
        menu_btn.set_popup(menu)
        self.headerbar.pack_end(menu_btn)

        self.sort_combo = Gtk.ComboBoxText()
        for sid, slabel in [("score", "Trending"), ("new", "Newest"), ("downloads", "Most Downloaded"), ("rating", "Top Rated"), ("name", "Name")]:
            self.sort_combo.append(sid, slabel)
        self.sort_combo.set_active_id("score")
        self.sort_combo.connect("changed", self._on_sort_changed)
        self.headerbar.pack_end(self.sort_combo)

    def _build_onboarding_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        box.set_size_request(400, -1)
        box.set_margin_start(40)
        box.set_margin_end(40)

        icon_path = Path(__file__).parent / "data" / "mint-hub.svg"
        if icon_path.exists():
            pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(icon_path), 80, 80, True)
            icon = Gtk.Image.new_from_pixbuf(pb)
        else:
            icon = Gtk.Image.new_from_icon_name("applications-other", Gtk.IconSize.DIALOG)
            icon.set_pixel_size(80)
        box.pack_start(icon, False, False, 0)

        title = Gtk.Label(label="Welcome to Linux Mint Hub")
        title.get_style_context().add_class("welcome-title")
        box.pack_start(title, False, False, 0)

        subtitle = Gtk.Label(label="Enter your OmniStream API key to connect to the enhancement marketplace")
        subtitle.get_style_context().add_class("welcome-subtitle")
        subtitle.set_line_wrap(True)
        subtitle.set_justify(Gtk.Justification.CENTER)
        box.pack_start(subtitle, False, False, 0)

        self.key_entry = Gtk.Entry()
        self.key_entry.set_placeholder_text("omni_live_...")
        self.key_entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self.key_entry.set_visibility(False)
        self.key_entry.connect("activate", self._on_connect_clicked)
        box.pack_start(self.key_entry, False, False, 8)

        link = Gtk.LinkButton.new_with_label(
            "https://omnistream.skinvaults.online",
            "Get your API key at omnistream.skinvaults.online"
        )
        box.pack_start(link, False, False, 0)

        self.connect_btn = Gtk.Button(label="Connect")
        self.connect_btn.get_style_context().add_class("suggested-action")
        self.connect_btn.connect("clicked", self._on_connect_clicked)
        box.pack_start(self.connect_btn, False, False, 8)

        self.key_error_label = Gtk.Label()
        self.key_error_label.get_style_context().add_class("error")
        self.key_error_label.set_visible(False)
        self.key_error_label.set_no_show_all(True)
        box.pack_start(self.key_error_label, False, False, 0)

        sep = Gtk.Separator()
        sep.set_margin_top(8)
        box.pack_start(sep, False, False, 0)

        local_btn = Gtk.Button(label="Browse Local Only")
        local_btn.set_tooltip_text("Skip marketplace connection — browse installed themes, Cinnamon Spices, and curated content")
        local_btn.connect("clicked", self._on_local_only)
        box.pack_start(local_btn, False, False, 4)

        self.stack.add_named(box, PAGE_ONBOARDING)

    def _build_loading_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        spinner = Gtk.Spinner()
        spinner.start()
        spinner.set_size_request(48, 48)
        box.pack_start(spinner, False, False, 0)
        self.loading_label = Gtk.Label(label="Scanning local enhancements...")
        box.pack_start(self.loading_label, False, False, 0)
        self.stack.add_named(box, PAGE_LOADING)

    def _build_home_page(self):
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        home_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        home_box.set_margin_top(16)
        home_box.set_margin_bottom(16)
        home_box.set_margin_start(24)
        home_box.set_margin_end(24)

        stats_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        stats_box.set_halign(Gtk.Align.CENTER)
        self._stat_widgets = {}
        for key, label, icon_name in [
            ("total", "Enhancements", "application-x-addon-symbolic"),
            ("installed", "Installed", "object-select-symbolic"),
            ("categories", "Categories", "view-grid-symbolic"),
        ]:
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            card.set_halign(Gtk.Align.CENTER)
            card.get_style_context().add_class("stat-card")
            val = Gtk.Label(label="0")
            val.get_style_context().add_class("stat-value")
            card.pack_start(val, False, False, 0)
            lbl = Gtk.Label(label=label)
            lbl.get_style_context().add_class("stat-label")
            card.pack_start(lbl, False, False, 0)
            stats_box.pack_start(card, True, True, 0)
            self._stat_widgets[key] = val
        home_box.pack_start(stats_box, False, False, 8)

        quick_btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        quick_btns.set_halign(Gtk.Align.CENTER)
        browse_all_btn = Gtk.Button(label="Browse All")
        browse_all_btn.get_style_context().add_class("suggested-action")
        browse_all_btn.connect("clicked", lambda w: self.navigate_to(PAGE_BROWSE))
        quick_btns.pack_start(browse_all_btn, False, False, 0)
        library_btn = Gtk.Button(label="My Library")
        library_btn.connect("clicked", lambda w: self.navigate_to(PAGE_LIBRARY))
        quick_btns.pack_start(library_btn, False, False, 0)
        home_box.pack_start(quick_btns, False, False, 0)

        trending_title = Gtk.Label(label="Trending")
        trending_title.set_xalign(0)
        trending_title.get_style_context().add_class("section-title")
        home_box.pack_start(trending_title, False, False, 0)

        trending_scroll = Gtk.ScrolledWindow()
        trending_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        trending_scroll.set_size_request(-1, 110)
        self.trending_flowbox = Gtk.FlowBox()
        self.trending_flowbox.set_min_children_per_line(3)
        self.trending_flowbox.set_max_children_per_line(20)
        self.trending_flowbox.set_homogeneous(True)
        self.trending_flowbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.trending_flowbox.connect("child-activated", self._on_tile_activated)
        trending_scroll.add(self.trending_flowbox)
        home_box.pack_start(trending_scroll, False, False, 0)

        cat_title = Gtk.Label(label="Categories")
        cat_title.set_xalign(0)
        cat_title.get_style_context().add_class("section-title")
        home_box.pack_start(cat_title, False, False, 0)

        self.categories_flowbox = Gtk.FlowBox()
        self.categories_flowbox.set_min_children_per_line(4)
        self.categories_flowbox.set_max_children_per_line(8)
        self.categories_flowbox.set_homogeneous(True)
        self.categories_flowbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.categories_flowbox.connect("child-activated", self._on_category_tile_activated)
        home_box.pack_start(self.categories_flowbox, False, False, 0)

        local_title = Gtk.Label(label="Installed Enhancements")
        local_title.set_xalign(0)
        local_title.get_style_context().add_class("section-title")
        home_box.pack_start(local_title, False, False, 0)

        self.home_installed_flowbox = Gtk.FlowBox()
        self.home_installed_flowbox.set_min_children_per_line(4)
        self.home_installed_flowbox.set_max_children_per_line(10)
        self.home_installed_flowbox.set_homogeneous(True)
        self.home_installed_flowbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.home_installed_flowbox.connect("child-activated", self._on_tile_activated)
        home_box.pack_start(self.home_installed_flowbox, True, True, 0)

        scroll.add(home_box)
        self.stack.add_named(scroll, PAGE_HOME)

    def _build_browse_page(self):
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)

        sidebar_scroll = Gtk.ScrolledWindow()
        sidebar_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sidebar_scroll.set_size_request(200, -1)

        self.category_listbox = Gtk.ListBox()
        self.category_listbox.get_style_context().add_class("category-sidebar")
        self.category_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)

        all_row = Gtk.ListBoxRow()
        all_label = Gtk.Label(label="  All Enhancements")
        all_label.set_xalign(0)
        all_row.add(all_label)
        all_row._cat_id = None
        self.category_listbox.add(all_row)

        self._sidebar_count_labels = {}
        for cat in CATEGORIES:
            row = Gtk.ListBoxRow()
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            icon = Gtk.Image.new_from_icon_name(cat["icon"], Gtk.IconSize.MENU)
            hbox.pack_start(icon, False, False, 4)
            label = Gtk.Label(label=cat["label"])
            label.set_xalign(0)
            hbox.pack_start(label, True, True, 0)
            count_lbl = Gtk.Label(label="")
            count_lbl.get_style_context().add_class("cat-count")
            hbox.pack_end(count_lbl, False, False, 4)
            self._sidebar_count_labels[cat["id"]] = count_lbl
            row.add(hbox)
            row._cat_id = cat["id"]
            self.category_listbox.add(row)

        self.category_listbox.connect("row-selected", self._on_sidebar_category_selected)
        sidebar_scroll.add(self.category_listbox)
        paned.pack1(sidebar_scroll, False, False)

        browse_scroll = Gtk.ScrolledWindow()
        browse_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.browse_flowbox = Gtk.FlowBox()
        self.browse_flowbox.set_min_children_per_line(4)
        self.browse_flowbox.set_max_children_per_line(10)
        self.browse_flowbox.set_row_spacing(2)
        self.browse_flowbox.set_column_spacing(2)
        self.browse_flowbox.set_homogeneous(True)
        self.browse_flowbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.browse_flowbox.connect("child-activated", self._on_tile_activated)

        browse_scroll.add(self.browse_flowbox)
        paned.pack2(browse_scroll, True, True)
        paned.set_position(200)

        self.stack.add_named(paned, PAGE_BROWSE)

    def _build_details_page(self):
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.detail_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.detail_box.set_margin_top(20)
        self.detail_box.set_margin_bottom(20)
        self.detail_box.set_margin_start(24)
        self.detail_box.set_margin_end(24)

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        self.detail_thumb = Gtk.Image()
        self.detail_thumb.set_size_request(128, 128)
        top.pack_start(self.detail_thumb, False, False, 0)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.detail_name = Gtk.Label()
        self.detail_name.set_xalign(0)
        self.detail_name.get_style_context().add_class("detail-title")
        info.pack_start(self.detail_name, False, False, 0)

        self.detail_author = Gtk.Label()
        self.detail_author.set_xalign(0)
        self.detail_author.get_style_context().add_class("detail-author")
        info.pack_start(self.detail_author, False, False, 0)

        self.detail_category_label = Gtk.Label()
        self.detail_category_label.set_xalign(0)
        self.detail_category_label.get_style_context().add_class("dim-label")
        info.pack_start(self.detail_category_label, False, False, 0)

        self.detail_rating_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        info.pack_start(self.detail_rating_box, False, False, 0)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_margin_top(8)

        self.install_btn = Gtk.Button(label="Install")
        self.install_btn.get_style_context().add_class("suggested-action")
        self.install_btn.connect("clicked", self._on_install_clicked)
        btn_box.pack_start(self.install_btn, False, False, 0)

        self.apply_btn = Gtk.Button(label="Apply")
        self.apply_btn.connect("clicked", self._on_apply_clicked)
        btn_box.pack_start(self.apply_btn, False, False, 0)

        self.revert_btn = Gtk.Button(label="Revert")
        self.revert_btn.get_style_context().add_class("destructive-action")
        self.revert_btn.connect("clicked", self._on_revert_clicked)
        btn_box.pack_start(self.revert_btn, False, False, 0)

        self.uninstall_btn = Gtk.Button(label="Uninstall")
        self.uninstall_btn.connect("clicked", self._on_uninstall_clicked)
        btn_box.pack_start(self.uninstall_btn, False, False, 0)

        self.fav_btn = Gtk.Button()
        self.fav_btn.set_image(Gtk.Image.new_from_icon_name("emblem-favorite-symbolic", Gtk.IconSize.BUTTON))
        self.fav_btn.set_tooltip_text("Add to favorites")
        self.fav_btn.connect("clicked", self._on_toggle_favorite)
        btn_box.pack_end(self.fav_btn, False, False, 0)

        info.pack_start(btn_box, False, False, 0)
        top.pack_start(info, True, True, 0)
        self.detail_box.pack_start(top, False, False, 0)

        self.detail_box.pack_start(Gtk.Separator(), False, False, 4)

        desc_title = Gtk.Label(label="Description")
        desc_title.set_xalign(0)
        desc_title.get_style_context().add_class("subheading")
        self.detail_box.pack_start(desc_title, False, False, 0)

        self.detail_desc = Gtk.Label()
        self.detail_desc.set_xalign(0)
        self.detail_desc.set_line_wrap(True)
        self.detail_desc.set_selectable(True)
        self.detail_box.pack_start(self.detail_desc, False, False, 0)

        self.detail_box.pack_start(Gtk.Separator(), False, False, 4)

        meta_title = Gtk.Label(label="Details")
        meta_title.set_xalign(0)
        meta_title.get_style_context().add_class("subheading")
        self.detail_box.pack_start(meta_title, False, False, 0)

        self.detail_meta_grid = Gtk.Grid()
        self.detail_meta_grid.set_column_spacing(12)
        self.detail_meta_grid.set_row_spacing(4)
        self.detail_box.pack_start(self.detail_meta_grid, False, False, 0)

        self.detail_box.pack_start(Gtk.Separator(), False, False, 4)

        ss_title = Gtk.Label(label="Screenshots")
        ss_title.set_xalign(0)
        ss_title.get_style_context().add_class("subheading")
        self.detail_box.pack_start(ss_title, False, False, 0)
        self._ss_title = ss_title

        ss_scroll = Gtk.ScrolledWindow()
        ss_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        ss_scroll.set_size_request(-1, 160)
        self.detail_screenshots_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        ss_scroll.add(self.detail_screenshots_box)
        self.detail_box.pack_start(ss_scroll, False, False, 0)
        self._ss_scroll = ss_scroll

        self.detail_box.pack_start(Gtk.Separator(), False, False, 4)

        reviews_title = Gtk.Label(label="Reviews")
        reviews_title.set_xalign(0)
        reviews_title.get_style_context().add_class("subheading")
        self.detail_box.pack_start(reviews_title, False, False, 0)

        self.detail_reviews_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.detail_box.pack_start(self.detail_reviews_box, False, False, 0)

        review_form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        review_form.set_margin_top(8)

        rating_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        rating_label = Gtk.Label(label="Your rating:")
        rating_label.get_style_context().add_class("dim-label")
        rating_box.pack_start(rating_label, False, False, 0)
        self._review_stars = []
        for i in range(5):
            star_btn = Gtk.Button()
            star_btn.set_image(Gtk.Image.new_from_icon_name("non-starred-symbolic", Gtk.IconSize.BUTTON))
            star_btn.set_relief(Gtk.ReliefStyle.NONE)
            star_btn.connect("clicked", self._on_review_star_clicked, i)
            rating_box.pack_start(star_btn, False, False, 0)
            self._review_stars.append(star_btn)
        self._review_rating = 0
        review_form.pack_start(rating_box, False, False, 0)

        self._review_entry = Gtk.Entry()
        self._review_entry.set_placeholder_text("Write a short review...")
        review_form.pack_start(self._review_entry, False, False, 0)

        submit_review = Gtk.Button(label="Submit Review")
        submit_review.connect("clicked", self._on_submit_review)
        review_form.pack_start(submit_review, False, False, 0)

        self.detail_box.pack_start(review_form, False, False, 0)

        scroll.add(self.detail_box)
        self.stack.add_named(scroll, PAGE_DETAILS)

    def _build_library_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(16)
        box.set_margin_start(24)
        box.set_margin_end(24)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        title = Gtk.Label(label="My Library")
        title.set_xalign(0)
        title.get_style_context().add_class("heading")
        header.pack_start(title, True, True, 0)
        self.library_filter = Gtk.ComboBoxText()
        for fid, flabel in [("installed", "Installed"), ("favorites", "Favorites"), ("all", "All")]:
            self.library_filter.append(fid, flabel)
        self.library_filter.set_active_id("installed")
        self.library_filter.connect("changed", lambda w: self._refresh_library())
        header.pack_end(self.library_filter, False, False, 0)
        box.pack_start(header, False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.library_flowbox = Gtk.FlowBox()
        self.library_flowbox.set_min_children_per_line(4)
        self.library_flowbox.set_max_children_per_line(10)
        self.library_flowbox.set_homogeneous(True)
        self.library_flowbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.library_flowbox.connect("child-activated", self._on_tile_activated)
        scroll.add(self.library_flowbox)
        box.pack_start(scroll, True, True, 0)

        self.stack.add_named(box, PAGE_LIBRARY)

    def _build_upload_page(self):
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        outer.set_margin_top(16)
        outer.set_margin_bottom(16)
        outer.set_margin_start(24)
        outer.set_margin_end(24)

        title = Gtk.Label(label="Upload Enhancement")
        title.set_xalign(0)
        title.get_style_context().add_class("heading")
        outer.pack_start(title, False, False, 0)

        subtitle = Gtk.Label(label="Package and publish your enhancement to the marketplace")
        subtitle.set_xalign(0)
        subtitle.get_style_context().add_class("dim-label")
        outer.pack_start(subtitle, False, False, 0)

        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(8)
        row = 0

        def add_label(text, r):
            lbl = Gtk.Label(label=text)
            lbl.set_xalign(1)
            lbl.get_style_context().add_class("dim-label")
            grid.attach(lbl, 0, r, 1, 1)

        add_label("Source Folder", row)
        self.upload_dir_chooser = Gtk.FileChooserButton(
            title="Select enhancement folder",
            action=Gtk.FileChooserAction.SELECT_FOLDER,
        )
        self.upload_dir_chooser.set_hexpand(True)
        grid.attach(self.upload_dir_chooser, 1, row, 1, 1)
        row += 1

        add_label("Thumbnail", row)
        self.upload_thumb_chooser = Gtk.FileChooserButton(
            title="Select thumbnail image",
            action=Gtk.FileChooserAction.OPEN,
        )
        img_filter = Gtk.FileFilter()
        img_filter.set_name("Images")
        for pattern in ("*.png", "*.jpg", "*.jpeg", "*.svg", "*.webp"):
            img_filter.add_pattern(pattern)
        self.upload_thumb_chooser.add_filter(img_filter)
        self.upload_thumb_chooser.set_hexpand(True)
        grid.attach(self.upload_thumb_chooser, 1, row, 1, 1)
        row += 1

        add_label("Name *", row)
        self.upload_name = Gtk.Entry()
        self.upload_name.set_placeholder_text("My Awesome Theme")
        self.upload_name.set_hexpand(True)
        self.upload_name.connect("changed", self._on_upload_name_changed)
        grid.attach(self.upload_name, 1, row, 1, 1)
        row += 1

        add_label("Slug *", row)
        self.upload_slug = Gtk.Entry()
        self.upload_slug.set_placeholder_text("my-awesome-theme")
        self.upload_slug.set_hexpand(True)
        grid.attach(self.upload_slug, 1, row, 1, 1)
        row += 1

        add_label("Category *", row)
        self.upload_category = Gtk.ComboBoxText()
        for cat in CATEGORIES:
            self.upload_category.append(cat["id"], cat["label"])
        self.upload_category.set_active(0)
        self.upload_category.set_hexpand(True)
        grid.attach(self.upload_category, 1, row, 1, 1)
        row += 1

        add_label("Version", row)
        self.upload_version = Gtk.Entry()
        self.upload_version.set_text("1.0.0")
        self.upload_version.set_hexpand(True)
        grid.attach(self.upload_version, 1, row, 1, 1)
        row += 1

        add_label("Author", row)
        self.upload_author = Gtk.Entry()
        self.upload_author.set_placeholder_text("Your name")
        self.upload_author.set_hexpand(True)
        grid.attach(self.upload_author, 1, row, 1, 1)
        row += 1

        add_label("Summary", row)
        self.upload_summary = Gtk.Entry()
        self.upload_summary.set_placeholder_text("A short one-line description")
        self.upload_summary.set_hexpand(True)
        grid.attach(self.upload_summary, 1, row, 1, 1)
        row += 1

        add_label("Description", row)
        desc_scroll = Gtk.ScrolledWindow()
        desc_scroll.set_size_request(-1, 100)
        desc_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.upload_description = Gtk.TextView()
        self.upload_description.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        desc_scroll.add(self.upload_description)
        desc_scroll.set_hexpand(True)
        grid.attach(desc_scroll, 1, row, 1, 1)
        row += 1

        add_label("License", row)
        self.upload_license = Gtk.ComboBoxText()
        for lid, llabel in [("GPL-3.0", "GPL 3.0"), ("MIT", "MIT"), ("CC-BY-4.0", "CC BY 4.0"), ("Apache-2.0", "Apache 2.0"), ("other", "Other")]:
            self.upload_license.append(lid, llabel)
        self.upload_license.set_active_id("GPL-3.0")
        self.upload_license.set_hexpand(True)
        grid.attach(self.upload_license, 1, row, 1, 1)
        row += 1

        add_label("Tags", row)
        self.upload_tags = Gtk.Entry()
        self.upload_tags.set_placeholder_text("dark, modern, flat (comma-separated)")
        self.upload_tags.set_hexpand(True)
        grid.attach(self.upload_tags, 1, row, 1, 1)
        row += 1

        outer.pack_start(grid, False, False, 0)

        self.upload_error_label = Gtk.Label()
        self.upload_error_label.get_style_context().add_class("error")
        self.upload_error_label.set_xalign(0)
        self.upload_error_label.set_line_wrap(True)
        self.upload_error_label.set_visible(False)
        self.upload_error_label.set_no_show_all(True)
        outer.pack_start(self.upload_error_label, False, False, 0)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_margin_top(8)

        self.publish_btn = Gtk.Button(label="Package & Publish")
        self.publish_btn.get_style_context().add_class("suggested-action")
        self.publish_btn.connect("clicked", self._on_publish_clicked)
        btn_box.pack_start(self.publish_btn, False, False, 0)

        reset_btn = Gtk.Button(label="Reset Form")
        reset_btn.connect("clicked", self._on_upload_reset)
        btn_box.pack_start(reset_btn, False, False, 0)

        outer.pack_start(btn_box, False, False, 0)

        scroll.add(outer)
        self.stack.add_named(scroll, PAGE_UPLOAD)

    def _on_upload_name_changed(self, entry):
        name = entry.get_text().strip()
        slug = name.lower().replace(" ", "-").replace("_", "-")
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        self.upload_slug.set_text(slug)

    def _on_upload_reset(self, widget):
        self.upload_dir_chooser.unselect_all()
        self.upload_thumb_chooser.unselect_all()
        self.upload_name.set_text("")
        self.upload_slug.set_text("")
        self.upload_category.set_active(0)
        self.upload_version.set_text("1.0.0")
        self.upload_author.set_text("")
        self.upload_summary.set_text("")
        buf = self.upload_description.get_buffer()
        buf.set_text("")
        self.upload_license.set_active_id("GPL-3.0")
        self.upload_tags.set_text("")
        self.upload_error_label.set_visible(False)

    def _on_publish_clicked(self, widget):
        source_dir = self.upload_dir_chooser.get_filename()
        if not source_dir:
            self._show_upload_error("Please select a source folder.")
            return

        name = self.upload_name.get_text().strip()
        slug = self.upload_slug.get_text().strip()
        category = self.upload_category.get_active_id()

        if not name or not slug or not category:
            self._show_upload_error("Name, slug, and category are required.")
            return

        desc_buf = self.upload_description.get_buffer()
        description = desc_buf.get_text(desc_buf.get_start_iter(), desc_buf.get_end_iter(), False)

        tags_text = self.upload_tags.get_text().strip()
        tags = [t.strip() for t in tags_text.split(",") if t.strip()] if tags_text else []

        manifest = {
            "slug": slug,
            "name": name,
            "category": category,
            "version": self.upload_version.get_text().strip() or "1.0.0",
            "author": self.upload_author.get_text().strip(),
            "summary": self.upload_summary.get_text().strip(),
            "description": description,
            "license": self.upload_license.get_active_id() or "GPL-3.0",
            "tags": tags,
        }

        errors = validate_manifest(manifest)
        if errors:
            self._show_upload_error("; ".join(errors))
            return

        thumbnail_path = self.upload_thumb_chooser.get_filename() or ""

        self.upload_error_label.set_visible(False)
        self.publish_btn.set_sensitive(False)
        self.publish_btn.set_label("Packaging...")
        self.show_progress("Packaging enhancement...", 0.1)

        from threading_utils import _async

        @_async
        def do_publish():
            try:
                GLib.idle_add(self.show_progress, "Scanning for safety issues...", 0.1)
                scan = scan_for_upload(source_dir)
                if not scan.safe:
                    GLib.idle_add(self._publish_done, False,
                                 f"Security scan blocked upload:\n{scan.summary}")
                    return
                if scan.warnings:
                    print(f"Upload scan warnings:\n{scan.summary}")

                GLib.idle_add(self.show_progress, "Creating package...", 0.2)
                archive_path = create_package(source_dir, manifest, thumbnail_path)

                GLib.idle_add(self.show_progress, "Uploading to marketplace...", 0.5)

                import base64
                from pathlib import Path
                archive_data = base64.b64encode(Path(archive_path).read_bytes()).decode()

                upload_body = dict(manifest)
                upload_body["package_data"] = archive_data
                if thumbnail_path:
                    thumb_data = base64.b64encode(Path(thumbnail_path).read_bytes()).decode()
                    upload_body["thumbnail_data"] = thumb_data

                result = self.app.api.upload(upload_body)

                GLib.idle_add(self.show_progress, "Published!", 1.0)
                GLib.idle_add(self._publish_done, True, "")

                Path(archive_path).unlink(missing_ok=True)
            except Exception as e:
                GLib.idle_add(self._publish_done, False, str(e))

        do_publish()

    def _publish_done(self, success, error_msg):
        self.publish_btn.set_sensitive(True)
        self.publish_btn.set_label("Package & Publish")
        self.hide_progress()
        if success:
            self._on_upload_reset(None)
            self.show_toast("Enhancement published successfully!", "success", 4000)
        else:
            self._show_upload_error(f"Upload failed: {error_msg}")

    def _show_upload_error(self, msg):
        self.upload_error_label.set_text(msg)
        self.upload_error_label.set_visible(True)

    def _build_settings_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(16)
        box.set_margin_start(24)
        box.set_margin_end(24)
        box.set_margin_bottom(16)

        title = Gtk.Label(label="Settings")
        title.set_xalign(0)
        title.get_style_context().add_class("heading")
        box.pack_start(title, False, False, 0)

        key_frame = Gtk.Frame(label="OmniStream API Key")
        key_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        key_box.set_margin_top(8)
        key_box.set_margin_bottom(8)
        key_box.set_margin_start(12)
        key_box.set_margin_end(12)
        self.settings_key_entry = Gtk.Entry()
        self.settings_key_entry.set_visibility(False)
        self.settings_key_entry.set_placeholder_text("omni_live_...")
        key_box.pack_start(self.settings_key_entry, True, True, 0)
        save_key_btn = Gtk.Button(label="Save")
        save_key_btn.connect("clicked", self._on_save_key)
        key_box.pack_start(save_key_btn, False, False, 0)
        key_frame.add(key_box)
        box.pack_start(key_frame, False, False, 0)

        cache_frame = Gtk.Frame(label="Cache")
        cache_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        cache_box.set_margin_top(8)
        cache_box.set_margin_bottom(8)
        cache_box.set_margin_start(12)
        cache_box.set_margin_end(12)
        clear_btn = Gtk.Button(label="Clear Thumbnail Cache")
        clear_btn.connect("clicked", self._on_clear_cache)
        cache_box.pack_start(clear_btn, False, False, 0)
        cache_frame.add(cache_box)
        box.pack_start(cache_frame, False, False, 0)

        update_frame = Gtk.Frame(label="Updates")
        update_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        update_box.set_margin_top(8)
        update_box.set_margin_bottom(8)
        update_box.set_margin_start(12)
        update_box.set_margin_end(12)
        self.update_status_label = Gtk.Label(label=f"Current version: {APP_VERSION}")
        self.update_status_label.set_xalign(0)
        update_box.pack_start(self.update_status_label, False, False, 0)
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.check_update_btn = Gtk.Button(label="Check for Updates")
        self.check_update_btn.connect("clicked", self._on_check_update)
        btn_row.pack_start(self.check_update_btn, False, False, 0)
        self.install_update_btn = Gtk.Button(label="Install Update")
        self.install_update_btn.get_style_context().add_class("suggested-action")
        self.install_update_btn.set_visible(False)
        self.install_update_btn.connect("clicked", self._on_install_update)
        btn_row.pack_start(self.install_update_btn, False, False, 0)
        update_box.pack_start(btn_row, False, False, 0)
        update_frame.add(update_box)
        box.pack_start(update_frame, False, False, 0)

        about_frame = Gtk.Frame(label="About")
        about_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        about_box.set_margin_top(8)
        about_box.set_margin_bottom(8)
        about_box.set_margin_start(12)
        about_box.set_margin_end(12)
        about_box.pack_start(Gtk.Label(label=f"Linux Mint Hub v{APP_VERSION}"), False, False, 0)
        about_box.pack_start(Gtk.Label(label="Enhancement Hub for Linux Mint"), False, False, 0)
        about_box.pack_start(Gtk.Label(label="Browse, install, and manage themes, icons, wallpapers & more"), False, False, 0)
        about_frame.add(about_box)
        box.pack_start(about_frame, False, False, 0)

        self.stack.add_named(box, PAGE_SETTINGS)

    # --- Navigation ---

    _NON_HISTORY_PAGES = {PAGE_ONBOARDING, PAGE_LOADING}

    def navigate_to(self, page: str, data=None):
        current = self.stack.get_visible_child_name()
        if current and current != page and current not in self._NON_HISTORY_PAGES:
            self._history.append(current)
        self.stack.set_visible_child_name(page)
        self.back_btn.set_visible(
            any(p not in self._NON_HISTORY_PAGES for p in self._history))
        if page == PAGE_DETAILS and data:
            self._show_detail(data)
        elif page == PAGE_BROWSE:
            self._refresh_browse()
        elif page == PAGE_LIBRARY:
            self._refresh_library()
        elif page == PAGE_HOME:
            self._refresh_home()

    def _on_back(self, widget):
        while self._history:
            page = self._history.pop()
            if page not in self._NON_HISTORY_PAGES:
                self.stack.set_visible_child_name(page)
                break
        self.back_btn.set_visible(
            any(p not in self._NON_HISTORY_PAGES for p in self._history))

    # --- Home page ---

    def _refresh_home(self):
        counts = self.app.cache.get_category_counts()
        total = sum(counts.values())
        installed = self.app.cache.get_installed_count()
        self._stat_widgets["total"].set_text(str(total))
        self._stat_widgets["installed"].set_text(str(installed))
        self._stat_widgets["categories"].set_text(str(len([c for c in counts if counts[c] > 0])))

        for child in self.trending_flowbox.get_children():
            self.trending_flowbox.remove(child)
        trending = self.app.cache.get_all(sort="score", limit=8)
        self._populate_flowbox_batch(self.trending_flowbox, trending)

        for child in self.categories_flowbox.get_children():
            self.categories_flowbox.remove(child)
        for cat in CATEGORIES:
            count = counts.get(cat["id"], 0)
            tile = CategoryTile(cat["id"], cat["label"], cat["icon"], count)
            self.categories_flowbox.add(tile)

        for child in self.home_installed_flowbox.get_children():
            self.home_installed_flowbox.remove(child)
        installed_items = self.app.cache.get_all(installed=True, limit=30)
        if installed_items:
            self._populate_flowbox_batch(self.home_installed_flowbox, installed_items)

    # --- Browse page ---

    def _refresh_browse(self):
        counts = self.app.cache.get_category_counts()
        for cat_id, lbl in self._sidebar_count_labels.items():
            c = counts.get(cat_id, 0)
            lbl.set_text(str(c) if c > 0 else "")

        query = self.search_entry.get_text().strip()
        if query:
            items = self.app.cache.search(query, self._current_category)
        else:
            items = self.app.cache.get_all(
                category=self._current_category,
                sort=self._current_sort,
                limit=200,
            )
        for child in self.browse_flowbox.get_children():
            self.browse_flowbox.remove(child)
        if not items:
            empty = Gtk.Label(label="No enhancements found")
            empty.get_style_context().add_class("empty-state")
            empty.set_margin_top(40)
            self.browse_flowbox.add(empty)
            empty.show()
        else:
            self._populate_flowbox_batch(self.browse_flowbox, items)

    def _populate_flowbox_batch(self, flowbox, items, batch_size=20):
        self._tile_batch = items
        self._tile_batch_idx = 0
        self._tile_target = flowbox
        self._add_tile_batch(batch_size)

    def _add_tile_batch(self, batch_size=20):
        end = min(self._tile_batch_idx + batch_size, len(self._tile_batch))
        for i in range(self._tile_batch_idx, end):
            tile = EnhancementTile(self._tile_batch[i])
            self._tile_target.add(tile)
        self._tile_batch_idx = end
        if self._tile_batch_idx < len(self._tile_batch):
            GLib.idle_add(self._add_tile_batch, batch_size,
                          priority=GLib.PRIORITY_DEFAULT_IDLE)

    # --- Detail page ---

    def _show_detail(self, enh: Enhancement):
        self._detail_enh = enh
        applied = self.app.scanner.detect_applied()

        self.detail_name.set_text(enh.name)
        self.detail_author.set_text(f"by {enh.author}" if enh.author else "")

        cat_info = CATEGORY_MAP.get(enh.category, {})
        self.detail_category_label.set_text(cat_info.get("label", enh.category))

        for child in self.detail_rating_box.get_children():
            self.detail_rating_box.remove(child)
        if enh.avg_rating > 0:
            for i in range(5):
                icon_name = "starred-symbolic" if i < round(enh.avg_rating) else "non-starred-symbolic"
                star = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.SMALL_TOOLBAR)
                self.detail_rating_box.pack_start(star, False, False, 0)
            count = Gtk.Label(label=f"  ({enh.num_reviews} reviews)")
            count.get_style_context().add_class("dim-label")
            self.detail_rating_box.pack_start(count, False, False, 0)
        self.detail_rating_box.show_all()

        source = enh.thumbnail_local or enh.thumbnail_url
        load_thumbnail_async(source, 128, lambda pb: self.detail_thumb.set_from_pixbuf(pb) if pb else None,
                             cat_info.get("icon", "application-x-addon"))

        self.detail_desc.set_text(enh.description or enh.summary or "No description available.")

        for child in self.detail_meta_grid.get_children():
            self.detail_meta_grid.remove(child)
        meta_rows = [
            ("Version", enh.version),
            ("Category", cat_info.get("label", enh.category)),
            ("License", enh.license),
            ("Downloads", str(enh.downloads)),
            ("Install Path", enh.install_path or "N/A"),
            ("Source", enh.source),
        ]
        for i, (key, val) in enumerate(meta_rows):
            k = Gtk.Label(label=key)
            k.set_xalign(1)
            k.get_style_context().add_class("detail-meta-key")
            k.set_margin_end(8)
            v = Gtk.Label(label=val)
            v.set_xalign(0)
            v.set_selectable(True)
            v.set_ellipsize(Pango.EllipsizeMode.END)
            v.get_style_context().add_class("detail-meta-val")
            self.detail_meta_grid.attach(k, 0, i, 1, 1)
            self.detail_meta_grid.attach(v, 1, i, 1, 1)
        self.detail_meta_grid.show_all()

        is_applied = applied.get(enh.category) == enh.name
        self.install_btn.set_visible(not enh.installed)
        self.uninstall_btn.set_visible(enh.installed and enh.writable)
        self.apply_btn.set_visible(enh.installed and enh.category in applied and not is_applied)
        self.revert_btn.set_visible(is_applied)

        is_fav = self.app.cache.is_favorite(enh.slug)
        icon_name = "emblem-favorite" if is_fav else "emblem-favorite-symbolic"
        self.fav_btn.set_image(Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON))
        self.fav_btn.set_tooltip_text("Remove from favorites" if is_fav else "Add to favorites")

        for child in self.detail_screenshots_box.get_children():
            self.detail_screenshots_box.remove(child)
        if enh.screenshots:
            self._ss_title.set_visible(True)
            self._ss_scroll.set_visible(True)
            for url in enh.screenshots[:6]:
                img = Gtk.Image()
                img.set_size_request(240, 150)
                self.detail_screenshots_box.pack_start(img, False, False, 0)
                load_thumbnail_async(url, 150, lambda pb, i=img: i.set_from_pixbuf(pb) if pb else None)
            self.detail_screenshots_box.show_all()
        else:
            self._ss_title.set_visible(False)
            self._ss_scroll.set_visible(False)

        self._review_rating = 0
        for star_btn in self._review_stars:
            star_btn.set_image(Gtk.Image.new_from_icon_name("non-starred-symbolic", Gtk.IconSize.BUTTON))
        self._review_entry.set_text("")
        self._load_reviews(enh)

    # --- Library ---

    def _refresh_library(self):
        for child in self.library_flowbox.get_children():
            self.library_flowbox.remove(child)
        active_filter = self.library_filter.get_active_id() or "installed"
        if active_filter == "favorites":
            items = self.app.cache.get_favorites()
            empty_text = "No favorites yet — add some from the browse page!"
        elif active_filter == "all":
            items = self.app.cache.get_all(limit=500)
            empty_text = "No enhancements found"
        else:
            items = self.app.cache.get_all(installed=True, limit=500)
            empty_text = "No installed enhancements found"
        if not items:
            empty = Gtk.Label(label=empty_text)
            empty.get_style_context().add_class("empty-state")
            empty.set_margin_top(40)
            self.library_flowbox.add(empty)
            empty.show()
        else:
            self._populate_flowbox_batch(self.library_flowbox, items)

    # --- Event Handlers ---

    def _on_tile_activated(self, flowbox, child):
        if isinstance(child, EnhancementTile):
            self.navigate_to(PAGE_DETAILS, child.enhancement)

    def _on_category_tile_activated(self, flowbox, child):
        if isinstance(child, CategoryTile):
            self._current_category = child.cat_id
            self._sync_sidebar_to_category()
            self.navigate_to(PAGE_BROWSE)

    def _sync_sidebar_to_category(self):
        for row in self.category_listbox.get_children():
            if getattr(row, "_cat_id", None) == self._current_category:
                self.category_listbox.select_row(row)
                return

    def _on_sidebar_category_selected(self, listbox, row):
        if row:
            self._current_category = getattr(row, "_cat_id", None)
            if self.stack.get_visible_child_name() == PAGE_BROWSE:
                self._refresh_browse()

    def _on_search_changed(self, entry):
        if self._search_timeout:
            GLib.source_remove(self._search_timeout)
        self._search_timeout = GLib.timeout_add(300, self._do_search)

    def _do_search(self):
        self._search_timeout = None
        if self.stack.get_visible_child_name() != PAGE_BROWSE:
            self.navigate_to(PAGE_BROWSE)
        else:
            self._refresh_browse()
        return False

    def _on_sort_changed(self, combo):
        self._current_sort = combo.get_active_id() or "score"
        if self.stack.get_visible_child_name() == PAGE_BROWSE:
            self._refresh_browse()

    def _on_local_only(self, widget):
        self.navigate_to(PAGE_LOADING)
        self.app.start_init_local_only()

    def _on_connect_clicked(self, widget):
        key = self.key_entry.get_text().strip()
        if not key:
            self._show_key_error("Please enter an API key")
            return
        self.connect_btn.set_sensitive(False)
        self.connect_btn.set_label("Connecting...")
        from threading_utils import _async
        @_async
        def validate():
            valid = self.app.try_connect(key)
            GLib.idle_add(self._on_connect_result, valid)
        validate()

    def _on_connect_result(self, valid):
        self.connect_btn.set_sensitive(True)
        self.connect_btn.set_label("Connect")
        if valid:
            self.key_error_label.set_visible(False)
            self.navigate_to(PAGE_LOADING)
            self.app.start_init()
        else:
            self._show_key_error("Invalid API key. Check your key and try again.")

    def _show_key_error(self, msg):
        self.key_error_label.set_text(msg)
        self.key_error_label.set_visible(True)

    def _on_install_clicked(self, widget):
        if not self._detail_enh:
            return
        enh = self._detail_enh
        self.install_btn.set_sensitive(False)
        self.install_btn.set_label("Installing...")
        self.progress_revealer.set_reveal_child(True)
        self.progress_bar.set_text(f"Installing {enh.name}...")

        from threading_utils import _async
        @_async
        def do_install():
            try:
                url = enh.download_url
                if not url and self.app.api:
                    try:
                        result = self.app.api.download(enh.slug)
                        url = result.get("url", "") if isinstance(result, dict) else ""
                    except Exception as api_err:
                        log.warning(f"API download failed for {enh.slug}: {api_err}")
                        GLib.idle_add(self._install_done, False, "Marketplace server is unavailable.")
                        return
                if not url:
                    GLib.idle_add(self._install_done, False, "No download available for this item.")
                    return
                def progress(frac):
                    GLib.idle_add(self.progress_bar.set_fraction, frac)
                success = self.app.installer.install_from_url(enh, url, progress)
                GLib.idle_add(self._install_done, success, "")
            except Exception as e:
                log.warning(f"Install failed for {enh.slug}: {e}")
                GLib.idle_add(self._install_done, False, f"Installation failed: {e}")
        do_install()

    def _install_done(self, success, error_msg=""):
        self.install_btn.set_sensitive(True)
        self.install_btn.set_label("Install")
        self.progress_revealer.set_reveal_child(False)
        if success and self._detail_enh:
            self.show_toast(f"{self._detail_enh.name} installed successfully!", "success")
            self._show_detail(self._detail_enh)
        elif not success:
            scan = self.app.installer.last_scan_result
            if scan and not scan.safe:
                dialog = Gtk.MessageDialog(
                    transient_for=self.window,
                    modal=True,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text="Installation Blocked — Security Issue",
                )
                dialog.format_secondary_text(scan.summary)
                dialog.run()
                dialog.destroy()
            else:
                msg = error_msg or "Installation failed. Check your internet connection."
                self.show_toast(msg, "error", 4000)

    def _on_apply_clicked(self, widget):
        if not self._detail_enh:
            return
        success = self.app.applier.apply(self._detail_enh)
        if success:
            self.show_toast(f"{self._detail_enh.name} applied!", "success")
            self._show_detail(self._detail_enh)
        else:
            self.show_toast("Failed to apply enhancement", "error")

    def _on_revert_clicked(self, widget):
        if not self._detail_enh:
            return
        prev = self.app.applier.get_previous(self._detail_enh.category)
        if prev:
            self.app.applier.revert(self._detail_enh.category, prev)
            self._show_detail(self._detail_enh)

    def _on_uninstall_clicked(self, widget):
        if not self._detail_enh:
            return
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Uninstall {self._detail_enh.name}?",
        )
        dialog.format_secondary_text("This will remove the enhancement files from your system.")
        response = dialog.run()
        dialog.destroy()
        if response == Gtk.ResponseType.YES:
            success = self.app.installer.uninstall(self._detail_enh)
            if success:
                self.show_toast(f"{self._detail_enh.name} uninstalled", "success")
                self._show_detail(self._detail_enh)
            else:
                self.show_toast("Failed to uninstall", "error")

    def _on_save_key(self, widget):
        key = self.settings_key_entry.get_text().strip()
        if key:
            self.app.save_key(key)
            self.show_toast("API key saved", "success")

    def _on_clear_cache(self, widget):
        from imaging import clear_cache
        import shutil
        from constants import THUMBNAIL_CACHE_DIR
        clear_cache()
        if THUMBNAIL_CACHE_DIR.exists():
            shutil.rmtree(THUMBNAIL_CACHE_DIR)
            THUMBNAIL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.show_toast("Thumbnail cache cleared", "success")

    def _on_check_update(self, widget):
        self.check_update_btn.set_sensitive(False)
        self.check_update_btn.set_label("Checking...")
        self._pending_update = None
        from threading_utils import _async
        @_async
        def do_check():
            info = check_for_update()
            GLib.idle_add(self._update_check_done, info)
        do_check()

    def _update_check_done(self, info):
        self.check_update_btn.set_sensitive(True)
        self.check_update_btn.set_label("Check for Updates")
        if info and info.get("url"):
            self._pending_update = info
            self.update_status_label.set_text(
                f"Update available: v{info['version']} (current: v{info['current']})")
            self.install_update_btn.set_visible(True)
            self.install_update_btn.show()
            self.show_toast(f"Update v{info['version']} available!", "success")
        elif info:
            self.update_status_label.set_text(
                f"v{info['version']} available but no .deb found")
            self.install_update_btn.set_visible(False)
        else:
            self.update_status_label.set_text(
                f"Current version: {APP_VERSION} (up to date)")
            self.install_update_btn.set_visible(False)
            self.show_toast("You're running the latest version", "success")

    def _on_install_update(self, widget):
        if not self._pending_update:
            return
        url = self._pending_update["url"]
        self.install_update_btn.set_sensitive(False)
        self.install_update_btn.set_label("Downloading...")
        self.progress_revealer.set_reveal_child(True)
        self.progress_bar.set_text("Downloading update...")
        from threading_utils import _async
        @_async
        def do_update():
            def progress(frac):
                GLib.idle_add(self.progress_bar.set_fraction, frac)
            success, msg = download_and_install(url, progress)
            GLib.idle_add(self._update_install_done, success, msg)
        do_update()

    def _update_install_done(self, success, msg):
        self.install_update_btn.set_sensitive(True)
        self.install_update_btn.set_label("Install Update")
        self.progress_revealer.set_reveal_child(False)
        if success:
            self.show_toast(msg, "success", 5000)
            self.update_status_label.set_text("Update installed! Please restart the app.")
            self.install_update_btn.set_visible(False)
        else:
            self.show_toast(msg, "error", 5000)

    def check_update_on_startup(self):
        from threading_utils import _async
        @_async
        def do_check():
            info = check_for_update()
            if info and info.get("url"):
                GLib.idle_add(self._startup_update_notify, info)
        do_check()

    def _startup_update_notify(self, info):
        self._pending_update = info
        self.update_status_label.set_text(
            f"Update available: v{info['version']} (current: v{info['current']})")
        self.install_update_btn.set_visible(True)
        self.install_update_btn.show()
        self.show_toast(f"Update v{info['version']} is available! Go to Settings to install.", "info", 5000)

    def show_progress(self, text: str, fraction: float):
        self.progress_bar.set_text(text)
        self.progress_bar.set_fraction(fraction)
        self.progress_revealer.set_reveal_child(True)

    def hide_progress(self):
        self.progress_revealer.set_reveal_child(False)

    def set_loading_text(self, text: str):
        self.loading_label.set_text(text)

    # --- Toast notifications ---

    def show_toast(self, message: str, toast_type: str = "info", duration: int = 3000):
        ctx = self.toast_label.get_style_context()
        for cls in ["toast-success", "toast-error"]:
            ctx.remove_class(cls)
        if toast_type == "success":
            ctx.add_class("toast-success")
        elif toast_type == "error":
            ctx.add_class("toast-error")
        self.toast_label.set_text(message)
        self.toast_revealer.set_reveal_child(True)
        if self._toast_timeout:
            GLib.source_remove(self._toast_timeout)
        self._toast_timeout = GLib.timeout_add(duration, self._hide_toast)

    def _hide_toast(self):
        self.toast_revealer.set_reveal_child(False)
        self._toast_timeout = None
        return False

    # --- Keyboard shortcuts ---

    # --- Favorites ---

    def _on_toggle_favorite(self, widget):
        if not self._detail_enh:
            return
        is_fav = self.app.cache.toggle_favorite(self._detail_enh.slug)
        icon_name = "emblem-favorite" if is_fav else "emblem-favorite-symbolic"
        self.fav_btn.set_image(Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON))
        self.fav_btn.set_tooltip_text("Remove from favorites" if is_fav else "Add to favorites")
        msg = "Added to favorites" if is_fav else "Removed from favorites"
        self.show_toast(msg, "success", 2000)

    # --- Reviews ---

    def _on_review_star_clicked(self, button, index):
        self._review_rating = index + 1
        for i, star_btn in enumerate(self._review_stars):
            icon_name = "starred-symbolic" if i <= index else "non-starred-symbolic"
            star_btn.set_image(Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON))

    def _on_submit_review(self, widget):
        if not self._detail_enh or not self.app.api:
            self.show_toast("Cannot submit review without marketplace connection", "error")
            return
        if self._review_rating == 0:
            self.show_toast("Please select a rating", "error")
            return
        comment = self._review_entry.get_text().strip()
        if not comment:
            self.show_toast("Please write a review comment", "error")
            return

        from threading_utils import _async
        enh = self._detail_enh
        rating = self._review_rating

        @_async
        def do_submit():
            try:
                self.app.api.submit_review(enh.slug, rating, comment, "user")
                GLib.idle_add(self.show_toast, "Review submitted!", "success", 3000)
                GLib.idle_add(self._review_entry.set_text, "")
                GLib.idle_add(self._load_reviews, enh)
            except Exception as e:
                GLib.idle_add(self.show_toast, f"Failed to submit review: {e}", "error", 4000)
        do_submit()

    def _load_reviews(self, enh: Enhancement):
        for child in self.detail_reviews_box.get_children():
            self.detail_reviews_box.remove(child)
        if not self.app.api:
            return

        from threading_utils import _async

        @_async
        def do_load():
            try:
                reviews = self.app.api.list_reviews(enh.slug)
                if isinstance(reviews, list):
                    GLib.idle_add(self._populate_reviews, reviews)
            except Exception:
                pass
        do_load()

    def _populate_reviews(self, reviews):
        for child in self.detail_reviews_box.get_children():
            self.detail_reviews_box.remove(child)
        if not reviews:
            empty = Gtk.Label(label="No reviews yet — be the first!")
            empty.get_style_context().add_class("dim-label")
            empty.set_xalign(0)
            self.detail_reviews_box.pack_start(empty, False, False, 0)
        else:
            for review in reviews[:10]:
                row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
                user_label = Gtk.Label(label=review.get("username", "Anonymous"))
                user_label.set_xalign(0)
                header.pack_start(user_label, False, False, 0)
                stars_box = Gtk.Box(spacing=1)
                r = review.get("rating", 0)
                for i in range(5):
                    ic = "starred-symbolic" if i < r else "non-starred-symbolic"
                    stars_box.pack_start(Gtk.Image.new_from_icon_name(ic, Gtk.IconSize.SMALL_TOOLBAR), False, False, 0)
                header.pack_start(stars_box, False, False, 4)
                row.pack_start(header, False, False, 0)
                comment_label = Gtk.Label(label=review.get("comment", ""))
                comment_label.set_xalign(0)
                comment_label.set_line_wrap(True)
                comment_label.get_style_context().add_class("dim-label")
                row.pack_start(comment_label, False, False, 0)
                self.detail_reviews_box.pack_start(row, False, False, 4)
        self.detail_reviews_box.show_all()

    def _on_key_press(self, widget, event):
        ctrl = event.state & Gdk.ModifierType.CONTROL_MASK
        key = event.keyval

        if ctrl and key == Gdk.KEY_f:
            self.search_entry.grab_focus()
            return True
        if ctrl and key == Gdk.KEY_r:
            self.app.refresh_catalog()
            self.show_toast("Refreshing catalog...", "info")
            return True
        if key == Gdk.KEY_F5:
            current = self.stack.get_visible_child_name()
            if current == PAGE_HOME:
                self._refresh_home()
            elif current == PAGE_BROWSE:
                self._refresh_browse()
            elif current == PAGE_LIBRARY:
                self._refresh_library()
            return True
        if key == Gdk.KEY_Escape:
            if self.search_entry.get_text():
                self.search_entry.set_text("")
                return True
            if self._history:
                self._on_back(None)
                return True
        return False
