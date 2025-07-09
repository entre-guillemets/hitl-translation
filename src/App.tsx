// src/App.tsx
import { Toaster } from 'react-hot-toast';
import { Navigate, Route, BrowserRouter as Router, Routes } from 'react-router-dom';
import { AppSidebar } from './components/app-sidebar';
import { ThemeProvider } from './components/theme-provider';
import { SidebarInset, SidebarProvider, SidebarTrigger, useSidebar } from './components/ui/sidebar';
import './index.css';
import { CommandCenter } from './pages/command-center/CommandCenter';
import QualityDashboard from './pages/quality-dashboard/QualityDashboard';
import QualityPrediction from './pages/quality-prediction/QualityPrediction';
import { RequestTranslation } from './pages/request-translation/RequestTranslation';
import { RLHFDashboard } from './pages/rlhf-dashboard/RLHFDashboard';
import { TranslationQA } from './pages/translation-qa/TranslationQA';

function AppContent() {
  const { state } = useSidebar();
  const isCollapsed = state === "collapsed";

  return (
    <>
      <AppSidebar />
      <SidebarInset>
        {/* Toggle button that moves with sidebar state */}
        <div 
          className={`fixed top-4 z-50 transition-all duration-300 ${
            isCollapsed ? 'left-4' : 'left-52'
          }`}
        >
          <SidebarTrigger className="p-2 rounded-md bg-background border border-border hover:bg-muted transition-all duration-200" />
        </div>

        {/* Main content area */}
        <div className="flex flex-1 flex-col gap-4 p-4 pt-16">
          <Routes>
            <Route path="/" element={<Navigate to="/request-translation" replace />} />
            <Route path="/request-translation" element={<RequestTranslation />} />
            <Route path="/quality-prediction" element={<QualityPrediction />} />
            <Route path="/translation-qa" element={<TranslationQA />} />
            <Route path="/quality-dashboard" element={<QualityDashboard />} />
            <Route path="/rlhf" element={<RLHFDashboard />} />
            <Route path="/command-center" element={<CommandCenter />} />
          </Routes>
          <Toaster />
        </div>
      </SidebarInset>
    </>
  );
}

function App() {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      <Router>
        <SidebarProvider>
          <AppContent />
        </SidebarProvider>
      </Router>
    </ThemeProvider>
  );
}

export default App;
