import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ThemeProvider, createTheme, alpha } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";

type Mode = "light" | "dark";
const ThemeModeContext = createContext<{mode:Mode;toggle:()=>void}>({mode:"light",toggle:()=>undefined});
export const useThemeMode=()=>useContext(ThemeModeContext);

export function PetroEdgeThemeProvider({children}:{children:ReactNode}){
 const [mode,setMode]=useState<Mode>(()=>{
  const stored=localStorage.getItem("petroedge_theme");
  return stored==="dark"||stored==="light"?stored:"light";
 });
 useEffect(()=>{
  document.documentElement.dataset.theme=mode;
  document.documentElement.style.colorScheme=mode;
 },[mode]);
 const toggle=()=>setMode(current=>{const next=current==="light"?"dark":"light";localStorage.setItem("petroedge_theme",next);return next;});
 const theme=useMemo(()=>{
  const dark=mode==="dark";
  const primary="#008A97";
  return createTheme({
   palette:{
    mode,
    primary:{main:primary,dark:dark?"#58D5DF":"#07535b",light:"#37B5C0",contrastText:"#ffffff"},
    secondary:{main:dark?"#F3B443":"#A96700",contrastText:dark?"#15100A":"#ffffff"},
    background:dark?{default:"#061316",paper:"#102529"}:{default:"#F3F6F7",paper:"#FFFFFF"},
    text:dark?{primary:"#F4FBFC",secondary:"#BDD0D3",disabled:"#80979B"}:{primary:"#10272A",secondary:"#465D61",disabled:"#7A8C8F"},
    divider:dark?"#2B474C":"#CCD9DC",
    action:{hover:dark?"rgba(134,221,228,.10)":"rgba(0,124,137,.07)",selected:dark?"rgba(134,221,228,.16)":"rgba(0,124,137,.12)",disabled:dark?"rgba(244,251,252,.38)":"rgba(16,39,42,.38)",disabledBackground:dark?"rgba(244,251,252,.08)":"rgba(16,39,42,.08)"}
   },
   shape:{borderRadius:12},
   typography:{fontFamily:["Inter","Segoe UI","Arial","sans-serif"].join(","),h3:{fontWeight:850,letterSpacing:"-.04em"},h4:{fontWeight:800,letterSpacing:"-.025em"},h5:{fontWeight:750},h6:{fontWeight:750},button:{textTransform:"none",fontWeight:700}},
   components:{
    MuiCssBaseline:{styleOverrides:{body:{backgroundImage:dark?"radial-gradient(circle at 12% 0%, rgba(0,138,151,.14), transparent 30%)":"radial-gradient(circle at 12% 0%, rgba(0,138,151,.08), transparent 32%)"},"::selection":{backgroundColor:alpha(primary,.28)}}},
    MuiPaper:{styleOverrides:{root:{backgroundImage:"none",borderColor:dark?"#2B474C":"#CCD9DC",color:dark?"#F4FBFC":"#10272A"}}},
    MuiCard:{styleOverrides:{root:{backgroundImage:"none",borderColor:dark?"#2B474C":"#CCD9DC"}}},
    MuiButton:{styleOverrides:{root:{borderRadius:10},contained:{boxShadow:"none"},outlined:{borderColor:dark?"#46666C":"#9CB2B6"}}},
    MuiChip:{styleOverrides:{root:{fontWeight:650},outlined:{borderColor:dark?"#46666C":"#9CB2B6"}}},
    MuiInputBase:{styleOverrides:{root:{color:dark?"#F4FBFC":"#10272A"}}},
    MuiInputLabel:{styleOverrides:{root:{color:dark?"#BDD0D3":"#465D61"}}},
    MuiTab:{styleOverrides:{root:{color:dark?"#BDD0D3":"#465D61","&.Mui-selected":{color:dark?"#7DE4EB":"#07535b"}}}},
    MuiTableCell:{styleOverrides:{root:{borderColor:dark?"#2B474C":"#D8E2E4"},head:{color:dark?"#F4FBFC":"#10272A",fontWeight:800}}},
    MuiAlert:{styleOverrides:{root:{color:dark?"#F4FBFC":undefined}}},
    MuiTooltip:{styleOverrides:{tooltip:{fontSize:12}}}
   }
  });
 },[mode]);
 return <ThemeModeContext.Provider value={{mode,toggle}}><ThemeProvider theme={theme}><CssBaseline/>{children}</ThemeProvider></ThemeModeContext.Provider>;
}
