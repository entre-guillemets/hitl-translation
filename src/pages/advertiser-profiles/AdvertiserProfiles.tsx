// src/pages/advertiser-profiles/AdvertiserProfiles.tsx
"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { Building2, Edit, Plus, Trash2 } from "lucide-react";
import React, { useEffect, useState } from "react";
import toast from "react-hot-toast";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8001";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type BrandTone = "AUTHORITATIVE" | "PLAYFUL" | "LUXURY" | "APPROACHABLE" | "TECHNICAL" | "BOLD";
type AdRegister = "FORMAL" | "INFORMAL" | "NEUTRAL";

interface AdvertiserProfile {
  id: string;
  brandName: string;
  brandTone: BrandTone;
  register: AdRegister;
  targetMarkets: string[];
  keyTerms: string[];
  tabooTerms: string[];
  policyNotes: string | null;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

const BRAND_TONE_LABELS: Record<BrandTone, string> = {
  AUTHORITATIVE: "Authoritative",
  PLAYFUL: "Playful",
  LUXURY: "Luxury",
  APPROACHABLE: "Approachable",
  TECHNICAL: "Technical",
  BOLD: "Bold",
};

const REGISTER_LABELS: Record<AdRegister, string> = {
  FORMAL: "Formal",
  INFORMAL: "Informal",
  NEUTRAL: "Neutral",
};

const TONE_COLORS: Record<BrandTone, string> = {
  AUTHORITATIVE: "bg-slate-700 text-slate-100",
  PLAYFUL: "bg-yellow-600 text-yellow-50",
  LUXURY: "bg-purple-700 text-purple-100",
  APPROACHABLE: "bg-green-700 text-green-100",
  TECHNICAL: "bg-blue-700 text-blue-100",
  BOLD: "bg-red-700 text-red-100",
};

const MARKET_LABELS: Record<string, string> = {
  JP: "Japanese",
  FR: "French",
  EN: "English",
  SW: "Swahili",
};

// ---------------------------------------------------------------------------
// Blank form state
// ---------------------------------------------------------------------------

const BLANK_FORM = {
  brandName: "",
  brandTone: "APPROACHABLE" as BrandTone,
  register: "NEUTRAL" as AdRegister,
  targetMarkets: [] as string[],
  keyTerms: "",
  tabooTerms: "",
  policyNotes: "",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const AdvertiserProfiles: React.FC = () => {
  const [profiles, setProfiles] = useState<AdvertiserProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState({ ...BLANK_FORM });
  const [saving, setSaving] = useState(false);

  // -------------------------------------------------------------------------
  // Data fetching
  // -------------------------------------------------------------------------

  const fetchProfiles = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/advertiser-profiles`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setProfiles(data.profiles ?? []);
    } catch (err) {
      toast.error("Failed to load advertiser profiles");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchProfiles(); }, []);

  // -------------------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------------------

  const openCreate = () => {
    setEditingId(null);
    setForm({ ...BLANK_FORM });
    setDialogOpen(true);
  };

  const openEdit = (p: AdvertiserProfile) => {
    setEditingId(p.id);
    setForm({
      brandName: p.brandName,
      brandTone: p.brandTone,
      register: p.register,
      targetMarkets: p.targetMarkets,
      keyTerms: p.keyTerms.join(", "),
      tabooTerms: p.tabooTerms.join(", "),
      policyNotes: p.policyNotes ?? "",
    });
    setDialogOpen(true);
  };

  const toggleMarket = (code: string) => {
    setForm((f) => ({
      ...f,
      targetMarkets: f.targetMarkets.includes(code)
        ? f.targetMarkets.filter((m) => m !== code)
        : [...f.targetMarkets, code],
    }));
  };

  const parseTerms = (raw: string) =>
    raw.split(",").map((t) => t.trim()).filter(Boolean);

  // -------------------------------------------------------------------------
  // Save (create or update)
  // -------------------------------------------------------------------------

  const handleSave = async () => {
    if (!form.brandName.trim()) {
      toast.error("Brand name is required");
      return;
    }
    setSaving(true);
    const payload = {
      brandName: form.brandName.trim(),
      brandTone: form.brandTone,
      adRegister: form.register,
      targetMarkets: form.targetMarkets,
      keyTerms: parseTerms(form.keyTerms),
      tabooTerms: parseTerms(form.tabooTerms),
      policyNotes: form.policyNotes.trim() || null,
    };

    try {
      const url = editingId
        ? `${API_BASE_URL}/api/advertiser-profiles/${editingId}`
        : `${API_BASE_URL}/api/advertiser-profiles`;
      const method = editingId ? "PUT" : "POST";
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      toast.success(editingId ? "Profile updated" : "Profile created");
      setDialogOpen(false);
      fetchProfiles();
    } catch {
      toast.error("Failed to save profile");
    } finally {
      setSaving(false);
    }
  };

  // -------------------------------------------------------------------------
  // Delete (soft)
  // -------------------------------------------------------------------------

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Deactivate "${name}"?`)) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/advertiser-profiles/${id}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      toast.success(`"${name}" deactivated`);
      fetchProfiles();
    } catch {
      toast.error("Failed to deactivate profile");
    }
  };

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Building2 className="h-6 w-6 text-muted-foreground" />
          <div>
            <h1 className="text-2xl font-semibold">Advertiser Profiles</h1>
            <p className="text-sm text-muted-foreground">
              Brand voice and policy constraints that govern transcreation and evaluation
            </p>
          </div>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button onClick={openCreate}>
              <Plus className="mr-2 h-4 w-4" />
              New Profile
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>{editingId ? "Edit Profile" : "New Advertiser Profile"}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 pt-2">
              {/* Brand Name */}
              <div className="space-y-1.5">
                <Label>Brand Name</Label>
                <Input
                  placeholder="e.g. Aurient Watches"
                  value={form.brandName}
                  onChange={(e) => setForm((f) => ({ ...f, brandName: e.target.value }))}
                />
              </div>

              {/* Tone + Register row */}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label>Brand Tone</Label>
                  <Select
                    value={form.brandTone}
                    onValueChange={(v) => setForm((f) => ({ ...f, brandTone: v as BrandTone }))}
                  >
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {(Object.keys(BRAND_TONE_LABELS) as BrandTone[]).map((t) => (
                        <SelectItem key={t} value={t}>{BRAND_TONE_LABELS[t]}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label>Register</Label>
                  <Select
                    value={form.register}
                    onValueChange={(v) => setForm((f) => ({ ...f, register: v as AdRegister }))}
                  >
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {(Object.keys(REGISTER_LABELS) as AdRegister[]).map((r) => (
                        <SelectItem key={r} value={r}>{REGISTER_LABELS[r]}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Target Markets */}
              <div className="space-y-1.5">
                <Label>Target Markets</Label>
                <div className="flex gap-2 flex-wrap">
                  {Object.entries(MARKET_LABELS).map(([code, label]) => (
                    <button
                      key={code}
                      type="button"
                      onClick={() => toggleMarket(code)}
                      className={`rounded-md border px-3 py-1 text-sm transition-colors ${
                        form.targetMarkets.includes(code)
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-border bg-background hover:bg-muted"
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Key Terms */}
              <div className="space-y-1.5">
                <Label>Key Terms <span className="text-muted-foreground font-normal">(comma-separated)</span></Label>
                <Input
                  placeholder="Aurient, precision, heritage"
                  value={form.keyTerms}
                  onChange={(e) => setForm((f) => ({ ...f, keyTerms: e.target.value }))}
                />
              </div>

              {/* Taboo Terms */}
              <div className="space-y-1.5">
                <Label>Taboo Terms <span className="text-muted-foreground font-normal">(comma-separated)</span></Label>
                <Input
                  placeholder="cheap, discount, sale"
                  value={form.tabooTerms}
                  onChange={(e) => setForm((f) => ({ ...f, tabooTerms: e.target.value }))}
                />
              </div>

              {/* Policy Notes */}
              <div className="space-y-1.5">
                <Label>Policy Notes</Label>
                <Textarea
                  placeholder="e.g. Never use informal contractions. No superlatives."
                  rows={3}
                  value={form.policyNotes}
                  onChange={(e) => setForm((f) => ({ ...f, policyNotes: e.target.value }))}
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
                <Button onClick={handleSave} disabled={saving}>
                  {saving ? "Saving…" : editingId ? "Save Changes" : "Create Profile"}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-5">
            <div className="text-3xl font-bold">{profiles.length}</div>
            <div className="text-sm text-muted-foreground mt-1">Active Profiles</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-5">
            <div className="text-3xl font-bold">
              {[...new Set(profiles.flatMap((p) => p.targetMarkets))].length}
            </div>
            <div className="text-sm text-muted-foreground mt-1">Target Markets</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-5">
            <div className="text-3xl font-bold">
              {profiles.reduce((acc, p) => acc + p.keyTerms.length, 0)}
            </div>
            <div className="text-sm text-muted-foreground mt-1">Total Key Terms</div>
          </CardContent>
        </Card>
      </div>

      {/* Profiles table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Registered Profiles</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-8 text-center text-muted-foreground">Loading…</div>
          ) : profiles.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">
              No profiles yet. Create one to start evaluating brand voice compliance.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Brand</TableHead>
                  <TableHead>Tone</TableHead>
                  <TableHead>Register</TableHead>
                  <TableHead>Markets</TableHead>
                  <TableHead>Key Terms</TableHead>
                  <TableHead>Taboo Terms</TableHead>
                  <TableHead className="w-20"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {profiles.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-medium">{p.brandName}</TableCell>
                    <TableCell>
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${TONE_COLORS[p.brandTone]}`}>
                        {BRAND_TONE_LABELS[p.brandTone]}
                      </span>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{REGISTER_LABELS[p.register]}</Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1 flex-wrap">
                        {p.targetMarkets.map((m) => (
                          <Badge key={m} variant="secondary" className="text-xs">{m}</Badge>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground max-w-[180px] truncate">
                      {p.keyTerms.join(", ") || "—"}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground max-w-[160px] truncate">
                      {p.tabooTerms.length > 0 ? (
                        <span className="text-destructive">{p.tabooTerms.join(", ")}</span>
                      ) : "—"}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button variant="ghost" size="icon" onClick={() => openEdit(p)}>
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="text-destructive hover:text-destructive"
                          onClick={() => handleDelete(p.id, p.brandName)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Profile detail cards */}
      {profiles.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {profiles.map((p) => (
            <Card key={p.id}>
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between">
                  <CardTitle className="text-base">{p.brandName}</CardTitle>
                  <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${TONE_COLORS[p.brandTone]}`}>
                    {BRAND_TONE_LABELS[p.brandTone]}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">
                  {REGISTER_LABELS[p.register]} register ·{" "}
                  {p.targetMarkets.map((m) => MARKET_LABELS[m] ?? m).join(", ")}
                </p>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                {p.keyTerms.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-1">Key Terms</p>
                    <div className="flex flex-wrap gap-1">
                      {p.keyTerms.map((t) => (
                        <Badge key={t} variant="secondary" className="text-xs">{t}</Badge>
                      ))}
                    </div>
                  </div>
                )}
                {p.tabooTerms.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-1">Taboo Terms</p>
                    <div className="flex flex-wrap gap-1">
                      {p.tabooTerms.map((t) => (
                        <Badge key={t} variant="destructive" className="text-xs">{t}</Badge>
                      ))}
                    </div>
                  </div>
                )}
                {p.policyNotes && (
                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-1">Policy Notes</p>
                    <p className="text-xs text-muted-foreground leading-relaxed">{p.policyNotes}</p>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};
