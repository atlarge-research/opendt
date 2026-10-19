// the browser's full screen, like a game; Grafana's kiosk mode (no menus, no bars) is on anyway
document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen();
