export function openLiveSocket(onMessage) {
  let socket = null;
  let retry = 0;
  let stopped = false;

  function connect() {
    if (stopped) return;
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    socket = new WebSocket(`${protocol}//${location.host}/telemetry/live`);
    socket.onmessage = (event) => {
      onMessage(JSON.parse(event.data));
    };
    socket.onclose = () => {
      if (!stopped) retry = window.setTimeout(connect, 1000);
    };
  }

  connect();
  return () => {
    stopped = true;
    window.clearTimeout(retry);
    socket?.close();
  };
}
