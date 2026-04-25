// src/pages/persona-transcreation/PersonaTranscreation.tsx
"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { AlertTriangle, CheckCircle2, Clock, Info, Play, ThumbsUp, XCircle } from "lucide-react";
import React, { useCallback, useEffect, useState } from "react";
import toast from "react-hot-toast";
import { useLocation } from "react-router-dom";
import type { Persona, PersonaTranscreationResult } from "../../services/api";
import { personaCrudService, personaTranscreationService } from "../../services/api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8001";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AdvertiserProfile {
  id: string;
  brandName: string;
}

type PersonaStatus = PersonaTranscreationResult["status"];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const TARGET_LANGUAGES = [
  { value: "jp", label: "Japanese (JP)" },
  { value: "fr", label: "French (FR)" },
  { value: "en", label: "English (EN)" },
  { value: "sw", label: "Swahili (SW)" },
];

function ScoreBadge({ score, max = 5 }: { score: number | null; max?: number }) {
  if (score === null || score === undefined) return <span className="text-muted-foreground text-xs">—</span>;
  const pct = score / max;
  const color =
    pct >= 0.7 ? "bg-green-500/20 text-green-400 border-green-500/30" :
    pct >= 0.5 ? "bg-yellow-500/20 text-yellow-400 border-yellow-500/30" :
    "bg-red-500/20 text-red-400 border-red-500/30";
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${color}`}>
      {score.toFixed(1)}/{max}
    </span>
  );
}

function DiffScore({ score }: { score: number | null }) {
  if (score === null || score === undefined) return <span className="text-muted-foreground text-xs">—</span>;
  // Lower similarity = more distinct = better
  const isGood = score < 0.7;
  const color = isGood
    ? "bg-green-500/20 text-green-400 border-green-500/30"
    : "bg-orange-500/20 text-orange-400 border-orange-500/30";
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium cursor-default ${color}`}>
            <Info className="h-3 w-3" />
            {score.toFixed(2)}
          </span>
        </TooltipTrigger>
        <TooltipContent>
          <p className="text-xs max-w-52">
            Avg cosine similarity vs other personas (lower = more distinct).{" "}
            {isGood ? "Good differentiation." : "Personas may be converging."}
          </p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

function StatusIcon({ status }: { status: PersonaStatus }) {
  switch (status) {
    case "COMPLETED":
      return <CheckCircle2 className="h-4 w-4 text-green-400" />;
    case "NEEDS_REVIEW":
      return <AlertTriangle className="h-4 w-4 text-yellow-400" />;
    case "FAILED":
      return <XCircle className="h-4 w-4 text-red-400" />;
    case "IN_PROGRESS":
    case "PENDING":
      return <Clock className="h-4 w-4 text-muted-foreground animate-pulse" />;
    default:
      return null;
  }
}

function statusLabel(status: PersonaStatus): string {
  switch (status) {
    case "COMPLETED": return "Completed";
    case "NEEDS_REVIEW": return "Needs Review";
    case "FAILED": return "Failed";
    case "IN_PROGRESS": return "In Progress";
    case "PENDING": return "Pending";
    default: return status;
  }
}

// ---------------------------------------------------------------------------
// Persona Card
// ---------------------------------------------------------------------------

interface PersonaCardProps {
  result: PersonaTranscreationResult;
  onApprove: (rowId: string) => void;
  approvingId: string | null;
}

function PersonaCard({ result, onApprove, approvingId }: PersonaCardProps) {
  const canApprove = result.status === "COMPLETED" || result.status === "NEEDS_REVIEW";
  const isApproving = approvingId === result.rowId;

  return (
    <Card className="flex flex-col h-full">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="text-base flex items-center gap-2">
              <StatusIcon status={result.status} />
              {result.personaName ?? "Unknown Persona"}
            </CardTitle>
            {result.psychographicDescription && (
              <p className="text-xs text-muted-foreground mt-1 leading-snug">
                {result.psychographicDescription}
              </p>
            )}
          </div>
          <Badge variant="outline" className="shrink-0 text-xs">
            {statusLabel(result.status)}
          </Badge>
        </div>

        {/* Scores row */}
        <div className="flex flex-wrap gap-3 mt-3 text-xs text-muted-foreground">
          <div className="flex items-center gap-1">
            <span>Brand Voice</span>
            <ScoreBadge score={result.brandVoiceScore} />
          </div>
          <div className="flex items-center gap-1">
            <span>Cultural Fit</span>
            <ScoreBadge score={result.culturalFitnessScore} />
          </div>
          <div className="flex items-center gap-1">
            <span>Distinction</span>
            <DiffScore score={result.differentiationScore} />
          </div>
        </div>

        {/* Flags */}
        {(result.tabooViolation || result.keyTermMissing) && (
          <div className="flex gap-2 mt-1">
            {result.tabooViolation && (
              <Badge variant="destructive" className="text-xs">Taboo violation</Badge>
            )}
            {result.keyTermMissing && (
              <Badge className="bg-orange-500/20 text-orange-400 border-orange-500/30 text-xs">Key term missing</Badge>
            )}
          </div>
        )}
      </CardHeader>

      <CardContent className="flex flex-col flex-1 gap-3">
        {/* Output text */}
        <div className="flex-1 rounded-md border bg-muted/30 p-3 text-sm min-h-24 whitespace-pre-wrap leading-relaxed">
          {result.outputText ?? (
            <span className="text-muted-foreground italic">
              {result.status === "PENDING" || result.status === "IN_PROGRESS"
                ? "Waiting for agent…"
                : "No output generated."}
            </span>
          )}
        </div>

        {/* Refinement summary */}
        {result.refinementAttempts > 0 && (
          <p className="text-xs text-muted-foreground">
            {result.refinementAttempts} refinement attempt{result.refinementAttempts !== 1 ? "s" : ""}
          </p>
        )}

        {/* NEEDS_REVIEW explanation */}
        {result.status === "NEEDS_REVIEW" && (
          <p className="text-xs text-yellow-400/80 bg-yellow-500/10 border border-yellow-500/20 rounded px-2 py-1.5">
            Did not reach quality threshold after max attempts. Human review required before TM promotion.
          </p>
        )}

        {/* Approve button */}
        {canApprove && result.outputText && (
          <Button
            size="sm"
            variant="outline"
            className="mt-auto gap-2"
            disabled={isApproving}
            onClick={() => onApprove(result.rowId)}
          >
            <ThumbsUp className="h-3.5 w-3.5" />
            {isApproving ? "Approving…" : "Approve & Add to TM"}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Log panel
// ---------------------------------------------------------------------------

interface LogEntry {
  type: string;
  message?: string;
  personaName?: string;
  [key: string]: unknown;
}

function AgentLog({ entries }: { entries: LogEntry[] }) {
  if (entries.length === 0) return null;
  return (
    <div className="rounded-md border bg-muted/20 p-3 space-y-1 max-h-48 overflow-y-auto text-xs font-mono">
      {entries.map((e, i) => {
        const prefix =
          e.type === "error" ? "🔴" :
          e.type === "done" ? "✅" :
          e.type === "persona_complete" ? "✓" :
          e.type === "persona_start" ? "▶" :
          "·";
        const text =
          e.message ??
          (e.type === "persona_complete"
            ? `${e.personaName}: ${(e as Record<string, unknown>).status} (BV ${((e as Record<string, unknown>).brandVoiceScore as number | null)?.toFixed(1) ?? "—"}/5)`
            : JSON.stringify(e));
        return (
          <div key={i} className={`flex gap-2 ${e.type === "error" ? "text-red-400" : e.type === "done" ? "text-green-400" : "text-muted-foreground"}`}>
            <span className="shrink-0">{prefix}</span>
            <span>{text}</span>
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function PersonaTranscreation() {
  const location = useLocation();
  const routeState = location.state as {
    translationStringId?: string;
    personaIds?: string[];
    targetLanguage?: string;
    advertiserProfileId?: string;
  } | null;

  const [profiles, setProfiles] = useState<AdvertiserProfile[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string>(routeState?.advertiserProfileId ?? "");
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [selectedPersonaIds, setSelectedPersonaIds] = useState<string[]>(routeState?.personaIds ?? []);
  const [translationStringId, setTranslationStringId] = useState(routeState?.translationStringId ?? "");
  const [targetLanguage, setTargetLanguage] = useState(routeState?.targetLanguage ?? "jp");

  const [results, setResults] = useState<PersonaTranscreationResult[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [isDone, setIsDone] = useState(false);
  const [logEntries, setLogEntries] = useState<LogEntry[]>([]);
  const [approvingId, setApprovingId] = useState<string | null>(null);

  // Load profiles on mount
  useEffect(() => {
    fetch(`${API_BASE_URL}/api/advertiser-profiles`)
      .then(r => r.json())
      .then(data => setProfiles(Array.isArray(data) ? data : data.profiles ?? []))
      .catch(() => toast.error("Failed to load advertiser profiles."));
  }, []);

  // Load personas when profile changes
  useEffect(() => {
    if (!selectedProfileId) {
      setPersonas([]);
      // Only reset selections if NOT pre-populated from route state
      if (!routeState?.personaIds) setSelectedPersonaIds([]);
      return;
    }
    personaCrudService.list(selectedProfileId)
      .then(setPersonas)
      .catch(() => toast.error("Failed to load personas."));
  }, [selectedProfileId]);

  // Auto-run if we arrived with a fully pre-populated state from the request form
  useEffect(() => {
    if (
      routeState?.translationStringId &&
      routeState?.personaIds?.length >= 2 &&
      routeState?.advertiserProfileId
    ) {
      // Small delay so the component finishes mounting
      const t = setTimeout(() => handleRun(), 300);
      return () => clearTimeout(t);
    }
  }, []); // intentionally empty — only fire once on mount

  const togglePersona = (id: string) => {
    setSelectedPersonaIds(prev =>
      prev.includes(id) ? prev.filter(p => p !== id) : [...prev, id]
    );
  };

  const addLog = useCallback((entry: LogEntry) => {
    setLogEntries(prev => [...prev, entry]);
  }, []);

  const updateResult = useCallback((personaId: string, patch: Partial<PersonaTranscreationResult>) => {
    setResults(prev => prev.map(r => r.personaId === personaId ? { ...r, ...patch } : r));
  }, []);

  const handleRun = async () => {
    if (!translationStringId.trim()) {
      toast.error("Enter a translation string ID.");
      return;
    }
    if (selectedPersonaIds.length < 2) {
      toast.error("Select at least 2 personas for comparison.");
      return;
    }

    setIsRunning(true);
    setIsDone(false);
    setLogEntries([]);
    // Seed result cards in pending state
    setResults(
      selectedPersonaIds.map(pid => {
        const persona = personas.find(p => p.id === pid);
        return {
          rowId: "",
          personaId: pid,
          personaName: persona?.name ?? pid,
          psychographicDescription: persona?.psychographicDescription ?? null,
          outputText: null,
          status: "PENDING",
          brandVoiceScore: null,
          culturalFitnessScore: null,
          differentiationScore: null,
          tabooViolation: null,
          keyTermMissing: null,
          refinementAttempts: 0,
          agentIterations: [],
        };
      })
    );

    try {
      await personaTranscreationService.runStream(
        {
          translationStringId: translationStringId.trim(),
          personaIds: selectedPersonaIds,
          targetLanguage,
        },
        (event) => {
          const e = event as Record<string, unknown>;
          addLog(event as LogEntry);

          if (e.type === "persona_start") {
            updateResult(e.personaId as string, { status: "IN_PROGRESS" });
          }
          if (e.type === "persona_complete") {
            updateResult(e.personaId as string, {
              status: e.status as PersonaStatus,
              outputText: e.outputText as string | null,
              brandVoiceScore: e.brandVoiceScore as number | null,
              culturalFitnessScore: e.culturalFitnessScore as number | null,
              differentiationScore: e.differentiationScore as number | null,
              refinementAttempts: e.refinementAttempts as number,
            });
          }
          if (e.type === "differentiation_computed") {
            const scores = e.scores as Record<string, number>;
            setResults(prev => prev.map(r => ({
              ...r,
              differentiationScore: r.personaName ? (scores[r.personaName] ?? r.differentiationScore) : r.differentiationScore,
            })));
          }
        },
        () => {
          setIsDone(true);
          setIsRunning(false);
          // Reload final state from DB
          personaTranscreationService.getComparison(translationStringId.trim())
            .then(data => setResults(data.personas))
            .catch(() => {/* best-effort */});
        },
        (err) => {
          toast.error(`Stream error: ${err.message}`);
          setIsRunning(false);
        },
      );
    } catch (err) {
      toast.error("Failed to start persona run.");
      setIsRunning(false);
    }
  };

  const handleApprove = async (rowId: string) => {
    setApprovingId(rowId);
    try {
      await personaTranscreationService.approve(rowId);
      toast.success("Approved and added to Translation Memory.");
      setResults(prev => prev.map(r => r.rowId === rowId ? { ...r, status: "COMPLETED" } : r));
    } catch {
      toast.error("Approval failed.");
    } finally {
      setApprovingId(null);
    }
  };

  const avgDiffScore = results.length > 1
    ? results.reduce((sum, r) => sum + (r.differentiationScore ?? 0), 0) / results.length
    : null;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Persona Transcreation</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Generate audience-segmented transcreations for a single source string across multiple buyer personas.
        </p>
      </div>

      {/* Configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>Translation String ID</Label>
              <Input
                placeholder="cuid..."
                value={translationStringId}
                onChange={e => setTranslationStringId(e.target.value)}
                disabled={isRunning}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Target Language</Label>
              <Select value={targetLanguage} onValueChange={setTargetLanguage} disabled={isRunning}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TARGET_LANGUAGES.map(l => (
                    <SelectItem key={l.value} value={l.value}>{l.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Advertiser Profile</Label>
            <Select value={selectedProfileId} onValueChange={setSelectedProfileId} disabled={isRunning}>
              <SelectTrigger>
                <SelectValue placeholder="Select a profile…" />
              </SelectTrigger>
              <SelectContent>
                {profiles.map(p => (
                  <SelectItem key={p.id} value={p.id}>{p.brandName}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {personas.length > 0 && (
            <div className="space-y-1.5">
              <Label>Select Personas (min 2)</Label>
              <div className="flex flex-wrap gap-2">
                {personas.map(p => {
                  const selected = selectedPersonaIds.includes(p.id);
                  return (
                    <button
                      key={p.id}
                      type="button"
                      disabled={isRunning}
                      onClick={() => togglePersona(p.id)}
                      className={`rounded-full border px-3 py-1 text-sm transition-colors ${
                        selected
                          ? "border-primary bg-primary/10 text-primary"
                          : "border-border text-muted-foreground hover:border-primary/50"
                      } disabled:opacity-50 disabled:cursor-not-allowed`}
                    >
                      {p.name}
                    </button>
                  );
                })}
              </div>
              {selectedPersonaIds.length > 0 && selectedPersonaIds.length < 2 && (
                <p className="text-xs text-yellow-400">Select at least 2 personas for differentiation scoring.</p>
              )}
            </div>
          )}

          {selectedProfileId && personas.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No personas configured for this profile. Add personas on the{" "}
              <a href="/advertiser-profiles" className="underline underline-offset-2">Advertiser Profiles</a> page.
            </p>
          )}

          <Button
            onClick={handleRun}
            disabled={isRunning || selectedPersonaIds.length < 2 || !translationStringId.trim()}
            className="gap-2"
          >
            <Play className="h-4 w-4" />
            {isRunning ? "Running…" : "Run Persona Fan-Out"}
          </Button>
        </CardContent>
      </Card>

      {/* Agent log */}
      {logEntries.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Agent Log</p>
          <AgentLog entries={logEntries} />
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold">Persona Outputs</h2>
            {avgDiffScore !== null && isDone && (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground cursor-default">
                      <Info className="h-4 w-4" />
                      Avg differentiation: <DiffScore score={avgDiffScore} />
                    </div>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p className="text-xs max-w-60">
                      Average pairwise similarity across all persona outputs.
                      Values below 0.7 indicate meaningful differentiation between personas.
                    </p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
          </div>

          {/* Evaluation mode note */}
          <div className="flex items-start gap-2 rounded-md border border-muted bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
            <Info className="h-3.5 w-3.5 mt-0.5 shrink-0" />
            <span>
              <strong>Multi-Agent Eval Mode:</strong> Brand Voice and Cultural Fitness scores are the primary quality
              signals here. BLEU/TER are not shown — surface-level fidelity metrics penalise intentional creative
              adaptation and are not meaningful for transcreation tasks.
            </span>
          </div>

          <div
            className={`grid gap-4 ${
              results.length === 2 ? "grid-cols-2" :
              results.length >= 3 ? "grid-cols-1 md:grid-cols-2 lg:grid-cols-3" :
              "grid-cols-1"
            }`}
          >
            {results.map(result => (
              <PersonaCard
                key={result.personaId}
                result={result}
                onApprove={handleApprove}
                approvingId={approvingId}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
