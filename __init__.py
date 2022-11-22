# -*- coding: utf-8 -*-
#
"""
Add-on package initialization
"""

import os
from glob import glob
import re
import shutil
import subprocess
import json
from functools import wraps

import anki
import aqt
import aqt.qt
from aqt import appVersion
from aqt import mw

app_version_micro = int(appVersion.rsplit('.', 1)[-1])

ADDON_PATH = os.path.dirname(__file__)
MODULE_ADDON = __name__.split(".")[0]
ICONS_PATH = os.path.join(ADDON_PATH, "icons")
ICON_PATH = os.path.join(ICONS_PATH, "unicorn.png")
config = mw.addonManager.getConfig(__name__)
open_shortcut = config["shortcuts"]["open"]
open_action_text = "&" + config["texts"]["open"]
open_menu_text = config["texts"]["open_menu"]
open_btn_text = config["texts"]["open_btn"]
open_hint_text = config["texts"]["open_hint"]

def check_browser():
    return aqt.dialogs._dialogs['Browser'][1]

# NOTE card() gets a user reviewing card and bcard() gets a user browsing card.
# If user uses reviewing and browsing at same time, they functions return
# different card ids. Context Menu can be uses preview window and review window.
# But Preview window follows Browser Window which can call bcard() function.
def card():
    #return self.reviewer.card.__dict__
    return aqt.mw.reviewer.card
def bcard(): #_debugBrowserCard(self):
    return aqt.dialogs._dialogs['Browser'][1].card

def search_in_org(file, note_id):
    try:
        data = open(file, "r").read()
    except Exception as e:
        print("Openfile: open: %s" % str(e))
        return None

    res = config["note_match"].format(note_id=note_id)
    found = re.compile(res, flags=re.MULTILINE).search(data)
    if found:
        return (found.start(0), found.end(0))

    return None


def lru_file_cache(func):
    func.cache = {}
    @wraps(func)
    def wrapper(*args):
        org_name = ""
        docs = (0, 0)
        size = 0
        mtime = 0

        cache_missed = True
        if args in func.cache:
            org_name, docs, size, mtime = func.cache[args]
            if os.path.exists(org_name) and (mtime == os.path.getmtime(org_name) or size == os.path.getsize(org_name)):
                cache_missed = False

        if cache_missed:
            # print('cache miss!')
            org_name, docs = func(*args)
            mtime = os.path.getmtime(org_name)
            size = os.path.getsize(org_name)
            func.cache[args] = (org_name, docs, size, mtime)
        return org_name, docs

    return wrapper

@lru_file_cache
def find_anki_note(note_id, org_dir='~/org'):
    search_path = os.path.expanduser(org_dir)
    use_ripgrep = config["use_ripgrep"]
    rg_opts = config["ripgrep_opts"].split(" ")
    if use_ripgrep and shutil.which(rg_opts[0]):
        pat = config["note_match"].format(note_id="(.+?)")
        rg_ret = subprocess.run(rg_opts.split(' ') + ['--json', pat, f'"{search_path}"'], stdout=subprocess.PIPE).stdout.decode('utf-8')
        for rg_line in rg_ret.split("\n"):
            rg_line = rg_line.strip()
            if not rg_line:
                continue

            js_line = json.loads(rg_line)
            if js_line["type"] != "match":
                continue

            org_name = js_line["data"]["path"]["text"]
            abs_offset = js_line["data"]["absolute_offset"]
            sub_start = js_line["data"]["submatches"][0]["start"]
            sub_end = js_line["data"]["submatches"][0]["end"]
            return org_name, (abs_offset + sub_start, abs_offset+sub_end)
    else:
        for org_name in glob(os.path.join(search_path, '**/*.org'), recursive=True):
            docs = search_in_org(org_name, note_id)
            if docs:
                return org_name, docs

    return None, None

def open_anki_note(note_id):
    found = False
    for org_dir in config["org-paths"]:
        org_file, found_note = find_anki_note(note_id, org_dir)
        # print('debug:', org_file, found_note)
        if org_file and found_note:
            char_pos = found_note[0]
            os.system(config["exec"].format(org_file=org_file, char_pos=char_pos))
            found = True
            break

    if not found:
        aqt.utils.showInfo(f'There is no org note for anki: {note_id}')


def tools_open_org_note():
    try:  # this works for web views in the reviewer and template dialog
        # print(f'MW STATE: {aqt.mw.state}')
        #if window is aqt.mw and aqt.mw.state == 'review':
        if aqt.mw.state == 'review':
            current_card = aqt.mw.reviewer.card
            # current_side = aqt.mw.reviewer.state
        elif aqt.mw.state == 'deckBrowser' or aqt.mw.state == 'overview':
            current_card = bcard()
            # current_side = aqt.mw.reviewer.state
        note_id = current_card.id
        # print('CARD ID::::', note_id)
        open_anki_note(note_id)
    except Exception:  # just in case, pylint:disable=broad-except
        pass

class OpenButton(aqt.qt.QPushButton):
    def __init__(self):
        super().__init__(aqt.qt.QIcon(ICON_PATH), open_btn_text)
        def request_open_note():
            if check_browser():
                note_id = bcard().id
                # print("CARD ID:", note_id)
                open_anki_note(note_id)

        self.clicked.connect(request_open_note)

def cards_button():
    from aqt import clayout

    clayout.CardLayout.setupButtons = anki.hooks.wrap(
        clayout.CardLayout.setupButtons,
        lambda card_layout: card_layout.buttons.insertWidget(
            # 3 if card_layout.buttons.count() in [6, 7] else 0,
            card_layout.buttons.count()-2,
            OpenButton(),
        ),
        'after',  # must use 'after' so that 'buttons' attribute is set
    )

def editor_button():
    def createOpenButton(editor):
        note_id = ''
        if check_browser():
            note_id = bcard().id
            # print("CARD ID:", note_id)
        else:
            note_id = card().id
            # print("EDITOR CARD:", note_id)
        open_anki_note(note_id)

    def addOpenButton(buttons, editor):
        new_button = editor.addButton(ICON_PATH,
                                      open_action_text,
                                      createOpenButton,
                                      tip = f"{open_hint_text} ({open_shortcut})",
                                      keys=open_shortcut)
        buttons.append(new_button)
        return buttons

    aqt.gui_hooks.editor_did_init_buttons.append(addOpenButton)

def reviewer_hooks():
    def on_context_menu(web_view, menu):
        window = web_view.window()
        def context_menu_open_note():
            try:  # this works for web views in the reviewer and template dialog
                if window is aqt.mw and aqt.mw.state == 'review':
                    current_card = aqt.mw.reviewer.card
                    # current_side = aqt.mw.reviewer.state
                elif aqt.mw.state == 'deckBrowser':
                    current_card = bcard()
                    # current_side = aqt.mw.reviewer.state
                elif web_view.objectName() == 'mainText':  # card template dialog
                    current_card = window.card
                note_id = current_card.id
                # print('CARD ID::::', note_id)
                open_anki_note(note_id)
            except Exception:  # just in case, pylint:disable=broad-except
                pass
        m = menu.addAction(open_action_text, context_menu_open_note)
        m.setShortcut(open_shortcut)
        m.setIcon(aqt.qt.QIcon(os.path.join(ICONS_PATH, "unicorn.png")))

    anki.hooks.addHook('AnkiWebView.contextMenuEvent', on_context_menu)
    anki.hooks.addHook('EditorWebView.contextMenuEvent', on_context_menu)
    anki.hooks.addHook('Reviewer.contextMenuEvent',
                       lambda reviewer, menu:
                       on_context_menu(reviewer.web, menu))

def preview_buttons():
    def setup_preview_slideshow(target_browser):
        "prepare when browser window shows up."
        def add_slideshow_ui_to_preview_window():
            if app_version_micro >= 24:
                preview_window = target_browser._previewer
                # from 2.1.24 we can reference bbox as attr
                bbox = preview_window.bbox
            else:
                preview_window = target_browser._previewWindow
                bbox = target_browser._previewNext.parentWidget()

            #open_button = bbox.addButton("Open org note", aqt.qt.QDialogButtonBox.ActionRole)
            bbox.addButton(OpenButton(), aqt.qt.QDialogButtonBox.ButtonRole.ActionRole)
            #open_button.setAutoDefault(True)
            # open_button.setToolTip("Open Org Note in Editor")
            #open_button.clicked.connect(request_open_note)

        original_preview_f = target_browser.onTogglePreview
        def onTogglePreview():
            original_preview_f()
            add_slideshow_ui_to_preview_window()
        target_browser.onTogglePreview = onTogglePreview


    from aqt import gui_hooks
    gui_hooks.browser_menus_did_init.append(setup_preview_slideshow)

def browser_menus():
    def on_setup_menus(browser):
        act = browser.form.menubar.addAction(open_action_text, tools_open_org_note)
        act.setIcon(aqt.qt.QIcon(ICON_PATH))
        m = browser.form.menubar.addMenu(open_menu_text)
        m.addAction(act)

    anki.hooks.addHook(
        'browser.setupMenus',
        on_setup_menus,
    )

def tools_menus():
    open_btn = aqt.qt.QAction(open_action_text, mw)
    open_btn.triggered.connect(tools_open_org_note)
    open_btn.setShortcut(open_shortcut)
    open_btn.setIcon(aqt.qt.QIcon(ICON_PATH))
    mw.form.menuTools.addAction(open_btn)

cards_button()
editor_button()
reviewer_hooks()
preview_buttons()
browser_menus()
tools_menus()
