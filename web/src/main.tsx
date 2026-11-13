import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { Client } from "./client";
import "./styles.css";

const client = new Client();

async function start() {
  await client.load();                 // the read cache: the app opens instantly, even offline
  void client.checkHealth();
  await client.sync();                 // tells us whether this device is signed in
  if (client.signedIn) void client.flush();
  if (location.search) history.replaceState(null, "", location.pathname + (client.signedIn ? "" : location.search));
}

createRoot(document.getElementById("root")!).render(
  <StrictMode><App client={client} /></StrictMode>,
);
void start();

if ("serviceWorker" in navigator && location.protocol === "https:") {
  navigator.serviceWorker.register("/sw.js").catch(() => { /* the app works without it */ });
}
