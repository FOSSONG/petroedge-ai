import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import "./styles.css";
import { queryClient } from "./query/queryClient";
import { PetroEdgeThemeProvider } from "./theme";

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("Unable to find the application root element (#root).");
ReactDOM.createRoot(rootElement).render(<React.StrictMode><QueryClientProvider client={queryClient}><PetroEdgeThemeProvider><App/></PetroEdgeThemeProvider></QueryClientProvider></React.StrictMode>);
