// src/components/app-sidebar.tsx
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
} from '@/components/ui/sidebar';
import { BarChart3, CheckSquare, ChevronRight, FileText } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ModeToggle } from './mode-toggle';

const API_BASE_URL = 'http://localhost:8001';

interface SystemStatus {
  status: string;
  database: string;
  cometkiwi_available: boolean;
  local_engines_available: boolean;
  available_engines: string[];
}

const StatusDot: React.FC<{ ok: boolean; label: string }> = ({ ok, label }) => (
  <div className="flex items-center gap-1.5">
    <span className={`inline-block h-2 w-2 rounded-full flex-shrink-0 ${ok ? 'bg-green-500' : 'bg-red-500'}`} />
    <span className="text-xs text-muted-foreground truncate">{label}</span>
  </div>
);

const SystemStatusWidget: React.FC = () => {
  const [status, setStatus] = useState<SystemStatus | null>(null);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/health/detailed`);
        if (res.ok) setStatus(await res.json());
      } catch { /* silently ignore */ }
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  if (!status) return null;

  const dbOk = status.database === 'connected';
  const engineCount = status.available_engines?.length ?? 0;

  return (
    <div className="px-2 pb-2">
      <p className="text-xs font-medium text-muted-foreground mb-1.5 px-1">System Status</p>
      <div className="rounded-md border bg-muted/30 px-2 py-2 space-y-1.5">
        <StatusDot ok={dbOk} label={dbOk ? 'Database' : 'Database error'} />
        <StatusDot ok={status.cometkiwi_available} label="COMETKiwi QE" />
        <StatusDot ok={status.local_engines_available} label={`MT Engines (${engineCount})`} />
      </div>
    </div>
  );
};

export const AppSidebar: React.FC = () => {
  const location = useLocation();

  return (
    <Sidebar>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <Link to="/">
                <div className="flex aspect-square size-8 items-center justify-center rounded-lg">
                  <img 
                    src="/favicon.svg" 
                    alt="Logo" 
                    className="h-6 w-6"
                  />
                </div>
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-semibold">MT Evals</span>
                  <span className="truncate text-xs">AI-Enabled QA Platform</span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Navigation</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {/* Preparing Translation Section */}
              <Collapsible defaultOpen className="group/collapsible">
                <SidebarMenuItem>
                  <CollapsibleTrigger asChild>
                    <SidebarMenuButton tooltip="Preparing Translation">
                      <FileText />
                      <span>Preparing Translation</span>
                      <ChevronRight className="ml-auto transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
                    </SidebarMenuButton>
                  </CollapsibleTrigger>
                  <CollapsibleContent>
                    <SidebarMenuSub>
                      <SidebarMenuSubItem>
                        <SidebarMenuSubButton asChild isActive={location.pathname === '/request-translation'}>
                          <Link to="/request-translation">
                            <span>Request Translation</span>
                          </Link>
                        </SidebarMenuSubButton>
                      </SidebarMenuSubItem>
                      <SidebarMenuSubItem>
                        <SidebarMenuSubButton asChild isActive={location.pathname === '/quality-prediction'}>
                          <Link to="/quality-prediction">
                            <span>Quality Prediction</span>
                          </Link>
                        </SidebarMenuSubButton>
                      </SidebarMenuSubItem>
                    </SidebarMenuSub>
                  </CollapsibleContent>
                </SidebarMenuItem>
              </Collapsible>

              {/* Translator Tools Section */}
              <Collapsible defaultOpen className="group/collapsible">
                <SidebarMenuItem>
                  <CollapsibleTrigger asChild>
                    <SidebarMenuButton tooltip="Translator Tools">
                      <CheckSquare />
                      <span>Translator Tools</span>
                      <ChevronRight className="ml-auto transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
                    </SidebarMenuButton>
                  </CollapsibleTrigger>
                  <CollapsibleContent>
                    <SidebarMenuSub>
                      <SidebarMenuSubItem>
                        <SidebarMenuSubButton asChild isActive={location.pathname === '/translation-qa'}>
                          <Link to="/translation-qa">
                            <span>MT Post-Editing</span>
                          </Link>
                        </SidebarMenuSubButton>
                      </SidebarMenuSubItem>
                      <SidebarMenuSubItem>
                        <SidebarMenuSubButton asChild isActive={location.pathname === '/command-center'}>
                          <Link to="/command-center">
                            <span>Command Center</span>
                          </Link>
                        </SidebarMenuSubButton>
                      </SidebarMenuSubItem>
                    </SidebarMenuSub>
                  </CollapsibleContent>
                </SidebarMenuItem>
              </Collapsible>

              {/* Insights Section */}
              <Collapsible defaultOpen className="group/collapsible">
                <SidebarMenuItem>
                  <CollapsibleTrigger asChild>
                    <SidebarMenuButton tooltip="Insights">
                      <BarChart3 />
                      <span>Insights</span>
                      <ChevronRight className="ml-auto transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
                    </SidebarMenuButton>
                  </CollapsibleTrigger>
                  <CollapsibleContent>
                    <SidebarMenuSub>
                      <SidebarMenuSubItem>
                        <SidebarMenuSubButton asChild isActive={location.pathname === '/quality-dashboard'}>
                          <Link to="/quality-dashboard">
                            <span>Evaluation Metrics</span>
                          </Link>
                        </SidebarMenuSubButton>
                      </SidebarMenuSubItem>
                      <SidebarMenuSubItem>
                        <SidebarMenuSubButton asChild isActive={location.pathname === '/rlhf'}>
                          <Link to="/rlhf">
                            <span>Human Preference Data</span>
                          </Link>
                        </SidebarMenuSubButton>
                      </SidebarMenuSubItem>
                    </SidebarMenuSub>
                  </CollapsibleContent>
                </SidebarMenuItem>
              </Collapsible>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      
      <SidebarFooter>
        <SystemStatusWidget />
        <SidebarMenu>
          <SidebarMenuItem>
            {/* FIXED: Removed SidebarMenuButton wrapper to avoid nested buttons */}
            <div className="flex items-center justify-between p-2">
              <span className="text-sm">Theme</span>
              <ModeToggle />
            </div>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
};
