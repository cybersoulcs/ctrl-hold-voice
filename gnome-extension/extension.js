const Main = imports.ui.main;
const St = imports.gi.St;
const GLib = imports.gi.GLib;
const Gio = imports.gi.Gio;

const STATUS_FILE = '/tmp/voice_status';

let _indicator = null;
let _timeoutId = null;
let _lastStatus = '';
let _indicatorIcon;
let _indicatorLabel;

function _getIcon(status) {
    switch (status) {
        case 'recording':    return 'audio-input-microphone-symbolic';
        case 'transcribing': return 'media-playlist-repeat-song-symbolic';
        case 'correcting':   return 'system-search-symbolic';
        case 'done':         return 'emblem-ok-symbolic';
        case 'error':        return 'dialog-warning-symbolic';
        default:             return 'audio-input-microphone-muted-symbolic';
    }
}

function _getStyle(status) {
    switch (status) {
        case 'recording':    return 'color: #ff4444; font-weight: bold;';
        case 'transcribing': return 'color: #ffaa00;';
        case 'correcting':   return 'color: #4488ff;';
        case 'done':         return 'color: #44dd44;';
        case 'error':        return 'color: #ff4444;';
        default:             return 'color: #888;';
    }
}

function _getText(status) {
    switch (status) {
        case 'recording':    return '\u25cf REC';
        case 'transcribing': return '\u21bb STT';
        case 'correcting':   return '\u2699 AI';
        case 'done':         return '\u2713';
        case 'error':        return '\u26a0';
        default:             return '';
    }
}

function _updateStatus() {
    let status = 'idle';
    try {
        let [, contents] = GLib.file_get_contents(STATUS_FILE);
        status = String.fromCharCode.apply(null, contents).trim();
    } catch (e) {
        status = 'idle';
    }

    if (status === _lastStatus) return true;
    _lastStatus = status;

    let text = _getText(status);
    if (status === 'idle' || !text) {
        _indicator.visible = false;
    } else {
        _indicator.visible = true;
        let gicon = Gio.Icon.new_for_string(_getIcon(status));
        _indicatorIcon.set_gicon(gicon);
        _indicatorLabel.set_text(' ' + text);
        _indicator.set_style(_getStyle(status));
    }
    return true;
}

function enable() {
    _indicator = new St.BoxLayout({ style_class: 'panel-button', reactive: false, visible: false });
    _indicatorIcon = new St.Icon({ icon_size: 16, style: 'padding-right: 2px;' });
    _indicatorLabel = new St.Label({ text: '', y_align: St.Align.MIDDLE });
    _indicator.add_child(_indicatorIcon);
    _indicator.add_child(_indicatorLabel);
    Main.panel._centerBox.insert_child_at_index(_indicator, 0);
    _updateStatus();
    _timeoutId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 300, () => {
        _updateStatus();
        return true;
    });
}

function disable() {
    if (_timeoutId) {
        GLib.source_remove(_timeoutId);
        _timeoutId = null;
    }
    if (_indicator) {
        Main.panel._centerBox.remove_child(_indicator);
        _indicator.destroy();
        _indicator = null;
    }
}
