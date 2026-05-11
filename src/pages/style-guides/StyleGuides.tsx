import { useEffect, useState } from 'react';
import { Plus, Trash2, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { API_BASE_URL } from '@/config/api';

const REGISTERS = ['FORMAL', 'INFORMAL', 'NEUTRAL', 'TECHNICAL', 'COLLOQUIAL'];
const TONES = ['AUTHORITATIVE', 'PLAYFUL', 'APPROACHABLE', 'BOLD', 'WARM', 'PRECISE'];

interface StyleGuideTerm {
  id: string;
  term: string;
  targetTerm: string | null;
  type: 'REQUIRED' | 'FORBIDDEN';
}

interface StyleGuide {
  id: string;
  name: string;
  description: string | null;
  styleRegister: string;
  tone: string | null;
  languagePairs: string[];
  rules: string[];
  isActive: boolean;
  terms: StyleGuideTerm[];
}

function TermBadge({ term }: { term: StyleGuideTerm }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
      term.type === 'REQUIRED'
        ? 'bg-green-900/40 text-green-300 border border-green-800'
        : 'bg-red-900/40 text-red-300 border border-red-800'
    }`}>
      {term.type === 'REQUIRED' ? '✓' : '✗'} {term.term}
      {term.targetTerm && <span className="opacity-60">→ {term.targetTerm}</span>}
    </span>
  );
}

function StyleGuideCard({ guide, onDelete }: { guide: StyleGuide; onDelete: () => void }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border border-border rounded-lg bg-card p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-sm">{guide.name}</span>
            <Badge variant="outline" className="text-xs">{guide.styleRegister}</Badge>
            {guide.tone && <Badge variant="outline" className="text-xs opacity-70">{guide.tone}</Badge>}
            {guide.languagePairs.length > 0 && guide.languagePairs.map(p => (
              <Badge key={p} variant="secondary" className="text-xs">{p.toUpperCase()}</Badge>
            ))}
          </div>
          {guide.description && (
            <p className="text-xs text-muted-foreground mt-1">{guide.description}</p>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setExpanded(e => !e)}>
            {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          </Button>
          <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive" onClick={onDelete}>
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {expanded && (
        <div className="space-y-2 pt-1 border-t border-border">
          {guide.rules.length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">Rules</p>
              <ul className="space-y-0.5">
                {guide.rules.map((rule, i) => (
                  <li key={i} className="text-xs text-foreground/80">• {rule}</li>
                ))}
              </ul>
            </div>
          )}
          {guide.terms.length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">Terms</p>
              <div className="flex flex-wrap gap-1.5">
                {guide.terms.map(t => <TermBadge key={t.id} term={t} />)}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function CreateGuideForm({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [styleRegister, setStyleRegister] = useState('NEUTRAL');
  const [tone, setTone] = useState('');
  const [rulesText, setRulesText] = useState('');
  const [saving, setSaving] = useState(false);

  const handleCreate = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      const rules = rulesText.split('\n').map(r => r.trim()).filter(Boolean);
      await fetch(`${API_BASE_URL}/api/style-guides`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim(), description: description.trim() || null, styleRegister, tone: tone || null, rules }),
      });
      setName(''); setDescription(''); setRulesText(''); setTone('');
      onCreated();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="border border-border rounded-lg bg-card p-4 space-y-3">
      <p className="text-sm font-medium">New Style Guide</p>
      <div className="grid grid-cols-2 gap-2">
        <Input placeholder="Name" value={name} onChange={e => setName(e.target.value)} className="text-sm" />
        <Input placeholder="Description (optional)" value={description} onChange={e => setDescription(e.target.value)} className="text-sm" />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Select value={styleRegister} onValueChange={setStyleRegister}>
          <SelectTrigger className="text-sm"><SelectValue /></SelectTrigger>
          <SelectContent>{REGISTERS.map(r => <SelectItem key={r} value={r}>{r}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={tone} onValueChange={setTone}>
          <SelectTrigger className="text-sm"><SelectValue placeholder="Tone (optional)" /></SelectTrigger>
          <SelectContent>{TONES.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
        </Select>
      </div>
      <textarea
        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm min-h-[72px] resize-y"
        placeholder="Rules — one per line (e.g. Use polite form in Japanese)"
        value={rulesText}
        onChange={e => setRulesText(e.target.value)}
      />
      <Button size="sm" onClick={handleCreate} disabled={saving || !name.trim()}>
        {saving ? 'Creating…' : 'Create Style Guide'}
      </Button>
    </div>
  );
}

export function StyleGuides() {
  const [guides, setGuides] = useState<StyleGuide[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/style-guides?active_only=false`);
      if (res.ok) setGuides(await res.json());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleDelete = async (id: string) => {
    await fetch(`${API_BASE_URL}/api/style-guides/${id}`, { method: 'DELETE' });
    setGuides(g => g.filter(s => s.id !== id));
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6 py-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Style Guides</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Reusable constraint sets — register, tone, rules, and term whitelists/blacklists — injected into LLM prompts at generation time.
          </p>
        </div>
        <Button size="sm" variant="outline" onClick={() => setShowCreate(s => !s)}>
          <Plus className="h-3.5 w-3.5 mr-1.5" />
          New Guide
        </Button>
      </div>

      {showCreate && (
        <CreateGuideForm onCreated={() => { setShowCreate(false); load(); }} />
      )}

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : guides.length === 0 ? (
        <p className="text-sm text-muted-foreground">No style guides yet. Create one to start applying constraints to LLM translations.</p>
      ) : (
        <div className="space-y-3">
          {guides.map(g => (
            <StyleGuideCard key={g.id} guide={g} onDelete={() => handleDelete(g.id)} />
          ))}
        </div>
      )}
    </div>
  );
}
