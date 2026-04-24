#!/usr/bin/env python3
import math
import sys
import traceback

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import Gdk, GdkPixbuf, GLib, Gtk


CARD_WIDTH = 250
CARD_HEIGHT = 330
CARD_SKEW = 34
NORMAL_SCALE = 0.88
ACTIVE_SCALE = 1.05
CARD_STEP = 168
SIDE_PADDING = 120
TITLE_GAP = 22


def eprint(*args):
    print(*args, file=sys.stderr, flush=True)


class ReelCard(Gtk.DrawingArea):
    def __init__(self, wallpaper_id: str, preview_path: str, title: str):
        super().__init__()
        self.wallpaper_id = wallpaper_id
        self.preview_path = preview_path
        self.title = title
        self.active = False

        self.normal_w = int(round(CARD_WIDTH * NORMAL_SCALE))
        self.normal_h = int(round(CARD_HEIGHT * NORMAL_SCALE))
        self.active_w = int(round(CARD_WIDTH * ACTIVE_SCALE))
        self.active_h = int(round(CARD_HEIGHT * ACTIVE_SCALE))

        slot_w = self.active_w + 40
        slot_h = self.active_h + 40
        self.set_size_request(slot_w, slot_h)

        self.add_events(
            Gdk.EventMask.ENTER_NOTIFY_MASK
            | Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.SCROLL_MASK
        )
        self.connect("draw", self.on_draw)

        original = GdkPixbuf.Pixbuf.new_from_file(preview_path)
        self.normal_pixbuf = self.scale_cover(original, self.normal_w, self.normal_h)
        self.active_pixbuf = self.scale_cover(original, self.active_w, self.active_h)

    @staticmethod
    def scale_cover(pixbuf: GdkPixbuf.Pixbuf, target_w: int, target_h: int) -> GdkPixbuf.Pixbuf:
        src_w = pixbuf.get_width()
        src_h = pixbuf.get_height()

        scale = max(target_w / src_w, target_h / src_h)
        scaled_w = max(1, int(math.ceil(src_w * scale)))
        scaled_h = max(1, int(math.ceil(src_h * scale)))

        scaled = pixbuf.scale_simple(
            scaled_w,
            scaled_h,
            GdkPixbuf.InterpType.BILINEAR,
        )

        crop_x = max(0, (scaled_w - target_w) // 2)
        crop_y = max(0, (scaled_h - target_h) // 2)
        return scaled.new_subpixbuf(crop_x, crop_y, target_w, target_h).copy()

    def set_active(self, active: bool):
        if self.active != active:
            self.active = active
            self.queue_draw()

    @staticmethod
    def draw_card_path(cr: cairo.Context, x: float, y: float, w: float, h: float, skew: float):
        cr.move_to(x + skew, y)
        cr.line_to(x + w, y)
        cr.line_to(x + w - skew, y + h)
        cr.line_to(x, y + h)
        cr.close_path()

    def on_draw(self, _widget, cr: cairo.Context):
        alloc = self.get_allocation()
        pixbuf = self.active_pixbuf if self.active else self.normal_pixbuf

        w = pixbuf.get_width()
        h = pixbuf.get_height()
        skew = CARD_SKEW * (ACTIVE_SCALE if self.active else NORMAL_SCALE)

        x = (alloc.width - w) / 2.0
        y = (alloc.height - h) / 2.0
        if self.active:
            y -= 7

        shadow_alpha = 0.28 if self.active else 0.20
        shadow_dx = 5 if self.active else 4
        shadow_dy = 13 if self.active else 10

        cr.save()
        self.draw_card_path(cr, x + shadow_dx, y + shadow_dy, w, h, skew)
        cr.set_source_rgba(0, 0, 0, shadow_alpha)
        cr.fill()
        cr.restore()

        cr.save()
        self.draw_card_path(cr, x, y, w, h, skew)
        cr.clip()
        Gdk.cairo_set_source_pixbuf(cr, pixbuf, x, y)
        cr.paint()
        cr.restore()

        cr.save()
        self.draw_card_path(cr, x, y, w, h, skew)
        if self.active:
            cr.set_source_rgba(1, 1, 1, 0.16)
            cr.set_line_width(1.4)
        else:
            cr.set_source_rgba(1, 1, 1, 0.06)
            cr.set_line_width(1.0)
        cr.stroke()
        cr.restore()

        return False


class Picker(Gtk.Window):
    def __init__(self, items_path: str):
        super().__init__(title="Wallpaper Engine Picker")

        self.selected_id = None
        self.focus_index = 0
        self.cards = []
        self.card_positions = []
        self.smooth_scroll_accum = 0.0

        self.items = self.load_items(items_path)
        if not self.items:
            raise RuntimeError("No items found in TSV")

        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_app_paintable(True)
        self.fullscreen()
        self.set_accept_focus(True)
        self.add_events(Gdk.EventMask.SCROLL_MASK)

        self.connect("destroy", Gtk.main_quit)
        self.connect("delete-event", self.on_delete)
        self.connect("key-press-event", self.on_key_press)
        self.connect("screen-changed", self.on_screen_changed)
        self.connect("realize", self.on_realize)
        self.connect("scroll-event", self.on_scroll)

        self.on_screen_changed()
        self.install_css()

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.set_hexpand(True)
        root.set_vexpand(True)
        self.add(root)

        root.pack_start(Gtk.Box(), True, True, 0)

        band = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        band.set_hexpand(True)
        band.set_halign(Gtk.Align.FILL)
        band.set_valign(Gtk.Align.CENTER)
        root.pack_start(band, False, False, 0)

        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.scroller.set_overlay_scrolling(True)
        self.scroller.set_shadow_type(Gtk.ShadowType.NONE)
        self.scroller.set_hexpand(True)
        self.scroller.set_vexpand(False)
        self.scroller.set_size_request(-1, int(round(CARD_HEIGHT * ACTIVE_SCALE)) + 50)
        self.scroller.connect("scroll-event", self.on_scroll)
        band.pack_start(self.scroller, False, False, 0)

        self.layout = Gtk.Layout()
        self.layout.set_hadjustment(self.scroller.get_hadjustment())
        self.layout.set_vadjustment(self.scroller.get_vadjustment())
        self.scroller.add(self.layout)

        valid_items = []
        x = SIDE_PADDING

        for item in self.items:
            wallpaper_id, preview, title = item
            try:
                card = ReelCard(wallpaper_id, preview, title)
            except Exception as exc:
                eprint(f"[picker] skipping preview {preview!r}: {exc}")
                continue

            index = len(valid_items)
            valid_items.append(item)
            self.cards.append(card)
            self.card_positions.append(x)

            self.layout.put(card, x, 0)
            card.connect("button-press-event", self.on_card_clicked, index)
            card.connect("enter-notify-event", self.on_card_hover, index)
            card.connect("scroll-event", self.on_scroll)

            x += CARD_STEP

        self.items = valid_items
        if not self.items:
            raise RuntimeError("No valid preview cards could be loaded")

        total_width = SIDE_PADDING * 2 + ((len(self.cards) - 1) * CARD_STEP) + self.cards[0].get_allocated_width()
        if total_width <= SIDE_PADDING * 2:
            total_width = SIDE_PADDING * 2 + 500
        self.layout.set_size(total_width, int(round(CARD_HEIGHT * ACTIVE_SCALE)) + 50)

        gap = Gtk.Box()
        gap.set_size_request(-1, TITLE_GAP)
        band.pack_start(gap, False, False, 0)

        self.title_label = Gtk.Label(label=self.items[0][2])
        self.title_label.set_halign(Gtk.Align.CENTER)
        band.pack_start(self.title_label, False, False, 0)

        root.pack_start(Gtk.Box(), True, True, 0)

        eprint(f"[picker] items loaded: {len(self.items)}")

        self.show_all()
        self.present()
        self.grab_focus()

        GLib.idle_add(self.update_focus, 0)
        GLib.idle_add(self.debug_visible)

    @staticmethod
    def load_items(items_path: str):
        eprint(f"[picker] reading: {items_path}")
        items = []
        with open(items_path, encoding="utf-8") as handle:
            for lineno, raw_line in enumerate(handle, start=1):
                line = raw_line.rstrip("\n")
                if not line:
                    continue

                parts = line.split("\t", 2)
                if len(parts) != 3:
                    eprint(f"[picker] malformed line {lineno}: {line!r}")
                    continue

                wallpaper_id, preview, title = parts
                if not wallpaper_id or not preview:
                    eprint(f"[picker] incomplete line {lineno}: {line!r}")
                    continue

                items.append((wallpaper_id, preview, title))
        return items

    def install_css(self):
        css = b"""
        window,
        box,
        layout,
        viewport,
        scrolledwindow,
        label {
            background-color: transparent;
            background: transparent;
            border: none;
            box-shadow: none;
        }

        scrolledwindow scrollbar,
        scrolledwindow undershoot,
        scrolledwindow overshoot {
            opacity: 0;
            min-width: 0;
            min-height: 0;
        }

        label {
            color: rgba(248, 242, 236, 0.96);
            font-family: "CaskaydiaCove Nerd Font", "Inter", sans-serif;
            font-size: 24px;
            font-weight: 500;
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        screen = Gdk.Screen.get_default()
        if screen is not None:
            Gtk.StyleContext.add_provider_for_screen(
                screen,
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

    def on_screen_changed(self, *_args):
        screen = self.get_screen()
        visual = screen.get_rgba_visual() if screen else None
        if visual and screen.is_composited():
            self.set_visual(visual)

    def on_realize(self, *_args):
        eprint("[picker] realized")

    def debug_visible(self):
        eprint("[picker] window shown")
        return False

    def on_delete(self, *_args):
        Gtk.main_quit()
        return False

    def move_strip(self, delta: float):
        adj = self.scroller.get_hadjustment()
        lower = adj.get_lower()
        upper = max(lower, adj.get_upper() - adj.get_page_size())
        value = min(max(adj.get_value() + delta, lower), upper)
        adj.set_value(value)

    def on_scroll(self, _widget, event):
        step = CARD_STEP * 0.95

        if event.direction == Gdk.ScrollDirection.SMOOTH:
            ok, dx, dy = event.get_scroll_deltas()
            if not ok:
                return False

            dominant = dx if abs(dx) >= abs(dy) else dy
            if abs(dominant) < 0.001:
                return False

            self.move_strip(dominant * step)
            self.smooth_scroll_accum += dominant

            if abs(self.smooth_scroll_accum) >= 0.60:
                self.shift_focus(1 if self.smooth_scroll_accum > 0 else -1)
                self.smooth_scroll_accum = 0.0
            return True

        if event.direction in {Gdk.ScrollDirection.UP, Gdk.ScrollDirection.LEFT}:
            self.move_strip(-step)
            self.shift_focus(-1)
            return True

        if event.direction in {Gdk.ScrollDirection.DOWN, Gdk.ScrollDirection.RIGHT}:
            self.move_strip(step)
            self.shift_focus(1)
            return True

        return False

    def on_key_press(self, _widget, event):
        key = Gdk.keyval_name(event.keyval)

        if key in {"Escape", "q"}:
            eprint("[picker] cancelled")
            Gtk.main_quit()
            return True

        if key in {"Right", "l"}:
            self.shift_focus(1)
            return True

        if key in {"Left", "h"}:
            self.shift_focus(-1)
            return True

        if key in {"Return", "KP_Enter", "space"} and self.items:
            self.selected_id = self.items[self.focus_index][0]
            eprint(f"[picker] selected via keyboard: {self.selected_id}")
            Gtk.main_quit()
            return True

        return False

    def on_card_hover(self, _widget, _event, index: int):
        self.update_focus(index)
        return False

    def on_card_clicked(self, _widget, event, index: int):
        if event.button == 1:
            self.focus_index = index
            self.selected_id = self.items[index][0]
            eprint(f"[picker] selected via click: {self.selected_id}")
            Gtk.main_quit()
            return True
        return False

    def shift_focus(self, delta: int):
        if not self.items:
            return
        self.focus_index = (self.focus_index + delta) % len(self.items)
        self.update_focus(self.focus_index)

    def update_focus(self, index: int):
        if not self.items:
            return False

        self.focus_index = index % len(self.items)
        self.title_label.set_text(self.items[self.focus_index][2])

        for i, card in enumerate(self.cards):
            card.set_active(i == self.focus_index)

        GLib.idle_add(self.scroll_focus_into_view)
        return False

    def scroll_focus_into_view(self):
        if not self.cards:
            return False

        adj = self.scroller.get_hadjustment()
        card_x = self.card_positions[self.focus_index]
        target_center = card_x + (self.cards[self.focus_index].get_allocated_width() / 2.0)
        target = target_center - (adj.get_page_size() / 2.0)

        lower = adj.get_lower()
        upper = max(lower, adj.get_upper() - adj.get_page_size())
        adj.set_value(min(max(target, lower), upper))
        return False


def main():
    if len(sys.argv) != 2:
        eprint(f"Usage: {sys.argv[0]} /path/to/items.tsv")
        return 2

    try:
        picker = Picker(sys.argv[1])
    except Exception:
        traceback.print_exc()
        return 2

    eprint("[picker] entering Gtk.main()")
    Gtk.main()
    eprint(f"[picker] Gtk.main() returned, selected_id={picker.selected_id!r}")

    if picker.selected_id:
        print(picker.selected_id, flush=True)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
