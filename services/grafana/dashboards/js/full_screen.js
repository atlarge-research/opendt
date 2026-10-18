// Grafana's kiosk mode (no menus, no bars; Esc leaves it) in the browser's full screen, like a game
const on = !document.fullscreenElement;
on ? document.documentElement.requestFullscreen() : document.exitFullscreen();
context.grafana.locationService.partial({ kiosk: on || null });
