# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tkinter as tk
from app_gui import SambungKataApp

def test_all_clean_windows():
    root = tk.Tk()
    root.withdraw()

    app = SambungKataApp(root)

    print("Testing window 1: open_gameplay_history_window")
    app.open_gameplay_history_window()
    assert app.gameplay_history_win is not None
    assert app.gameplay_history_win.winfo_exists()
    assert app.gameplay_history_win.overrideredirect()
    app.gameplay_history_win.destroy()

    print("Testing window 2: open_gameplay_classifier_window")
    app.open_gameplay_classifier_window()
    assert app.classifier_win is not None
    assert app.classifier_win.winfo_exists()
    assert app.classifier_win.overrideredirect()
    app.classifier_win.destroy()

    print("Testing window 3: open_blacklist_window")
    app.open_blacklist_window()
    assert app.blacklist_win is not None
    assert app.blacklist_win.winfo_exists()
    assert app.blacklist_win.overrideredirect()
    app.blacklist_win.destroy()

    print("Testing window 4: open_whitelist_window")
    app.open_whitelist_window()
    assert app.whitelist_win is not None
    assert app.whitelist_win.winfo_exists()
    assert app.whitelist_win.overrideredirect()
    app.whitelist_win.destroy()

    print("Testing window 5: open_custom_categories_window")
    app.open_custom_categories_window()
    assert app.custom_cats_win is not None
    assert app.custom_cats_win.winfo_exists()
    assert app.custom_cats_win.overrideredirect()
    
    print("Testing window 6: open_edit_custom_category_dialog")
    if app.config.get("custom_trap_endings"):
        app.open_edit_custom_category_dialog(0)
    app.custom_cats_win.destroy()

    print("Testing window 7: open_koreksi_window")
    app.open_koreksi_window()
    assert app.koreksi_win is not None
    assert app.koreksi_win.winfo_exists()
    assert app.koreksi_win.overrideredirect()
    app.koreksi_win.destroy()

    print("Testing window 8: open_add_word_dialog")
    app.open_add_word_dialog()
    assert app.add_word_win is not None
    assert app.add_word_win.winfo_exists()
    assert app.add_word_win.overrideredirect()
    app.add_word_win.destroy()

    print("Testing window 9: show_update_dialog")
    app.show_update_dialog({"has_update": False, "commits": [], "behind_count": 0, "branch": "main"})
    assert app.update_win is not None
    assert app.update_win.winfo_exists()
    assert app.update_win.overrideredirect()
    app.update_win.destroy()

    print("Testing window 10: open_dictionary_browser_window")
    app.open_dictionary_browser_window()
    assert app.dict_win is not None
    assert app.dict_win.winfo_exists()
    assert app.dict_win.overrideredirect()
    app.dict_win.destroy()

    print("Testing window 11: open_brutal_settings_window")
    app.open_brutal_settings_window()
    assert app.brutal_win is not None
    assert app.brutal_win.winfo_exists()
    assert app.brutal_win.overrideredirect()
    app.brutal_win.destroy()

    # Test mode switching
    print("Testing mode switching: Default -> Santai -> Brutal -> Default")
    app.set_game_mode("default")
    assert app.config.get("game_mode") == "default"
    assert not app.mode_santai_var.get()

    app.set_game_mode("santai")
    assert app.config.get("game_mode") == "santai"
    assert app.mode_santai_var.get()

    app.set_game_mode("brutal")
    assert app.config.get("game_mode") == "brutal"
    assert not app.mode_santai_var.get()

    app.cycle_game_mode()  # Should go from brutal to default
    assert app.config.get("game_mode") == "default"

    # Test custom tag sorting by length
    print("Testing custom tag sorting by length: Terpanjang & Tersedikit")
    app._on_sort_custom_categories_length(reverse=True)
    cats_long = app.config.get("custom_trap_endings", [])
    lens_long = [len(c.get("suffix", "")) for c in cats_long]
    assert lens_long == sorted(lens_long, reverse=True), "Tag length sort (descending) failed"

    app._on_sort_custom_categories_length(reverse=False)
    cats_short = app.config.get("custom_trap_endings", [])
    lens_short = [len(c.get("suffix", "")) for c in cats_short]
    assert lens_short == sorted(lens_short), "Tag length sort (ascending) failed"

    root.destroy()
    print("ALL 11 CLEAN WINDOWS, MODES, & TAG SORTS VERIFIED SUCCESSFULLY!")

if __name__ == "__main__":
    test_all_clean_windows()
