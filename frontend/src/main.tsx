import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import PilotAuthApp from "./auth/PilotAuthApp";
import "./styles.css";
const pilot = import.meta.env.VITE_PILOT_OIDC_ENABLED === 'true';
createRoot(document.getElementById("root")!).render(<StrictMode>{pilot ? <PilotAuthApp /> : <App />}</StrictMode>);
