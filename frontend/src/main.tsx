import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router';
import { App } from './routes/App';
import './index.css';

const query = new QueryClient();
createRoot(document.getElementById('root')!).render(
  <StrictMode><QueryClientProvider client={query}><BrowserRouter><App /></BrowserRouter></QueryClientProvider></StrictMode>
);
