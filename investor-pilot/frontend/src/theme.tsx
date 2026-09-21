import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { CssBaseline } from "@mui/material";
import { ThemeProvider, createTheme } from "@mui/material/styles";

interface ThemeContextValue { mode: "light" | "dark"; toggleMode: () => void; }
const PetroEdgeThemeContext = createContext<ThemeContextValue>({ mode: "light", toggleMode: () => undefined });
export const usePetroEdgeTheme = () => useContext(PetroEdgeThemeContext);

export function PetroEdgeThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<"light" | "dark">(() => localStorage.getItem("petroedge_theme") === "dark" ? "dark" : "light");
  const toggleMode = () => setMode((current) => { const next = current === "light" ? "dark" : "light"; localStorage.setItem("petroedge_theme", next); return next; });
  const theme = useMemo(() => createTheme({
    palette: mode === "dark" ? {
      mode, primary: { main: "#37c8d4", dark: "#1599a4" }, secondary: { main: "#f2b544" },
      background: { default: "#091317", paper: "#102127" }, text: { primary: "#f4fbfc", secondary: "#b8cbd0" }, divider: "#294149",
    } : {
      mode, primary: { main: "#007C89", dark: "#07535b" }, secondary: { main: "#B96F00" },
      background: { default: "#F3F7F8", paper: "#FFFFFF" }, text: { primary: "#10282d", secondary: "#4e656b" }, divider: "#cfdbde",
    },
    shape: { borderRadius: 12 },
    typography: { fontFamily: ["Inter","Segoe UI","Arial","sans-serif"].join(","), h3: { fontWeight: 850 }, h4: { fontWeight: 800 }, h5: { fontWeight: 750 }, h6: { fontWeight: 750 }, button: { textTransform: "none", fontWeight: 700 } },
    components: {
      MuiPaper: { styleOverrides: { root: ({ theme }) => ({ backgroundImage: "none", borderColor: theme.palette.divider }) } },
      MuiButton: { styleOverrides: { root: { borderRadius: 10 } } }, MuiChip: { styleOverrides: { root: { fontWeight: 650 } } },
      MuiAppBar: { styleOverrides: { root: ({ theme }) => ({ backgroundColor: theme.palette.background.paper, color: theme.palette.text.primary }) } },
      MuiTableCell: { styleOverrides: { root: ({ theme }) => ({ borderColor: theme.palette.divider }) } },
    },
  }), [mode]);
  return <PetroEdgeThemeContext.Provider value={{ mode, toggleMode }}><ThemeProvider theme={theme}><CssBaseline/>{children}</ThemeProvider></PetroEdgeThemeContext.Provider>;
}
