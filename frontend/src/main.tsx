import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import App from './App';
import './styles.css';

const queryClient = new QueryClient();

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: '#007C89' },
    secondary: { main: '#D98E04' },
    background: { default: '#F7F8FA' }
  },
  shape: { borderRadius: 6 },
  typography: {
    fontFamily: ['Inter', 'Segoe UI', 'Arial', 'sans-serif'].join(','),
    h5: { fontWeight: 700 },
    h6: { fontWeight: 700 }
  }
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </ThemeProvider>
  </React.StrictMode>
);

