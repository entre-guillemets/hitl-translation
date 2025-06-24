// src/pages/command-center/CommandCenter.tsx

"use client"

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { MultiSelect } from '@/components/ui/multi-select';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { AlertTriangle, CheckCircle, Download, Edit, FileDown, Plus, RefreshCw, Search, Trash2, Upload, XCircle } from 'lucide-react';
import React, { useEffect, useMemo, useRef, useState } from 'react';

// API Configuration
const API_BASE_URL = 'http://localhost:8001';

// Language Options
const languageOptions = [
  { label: 'English', value: 'EN' },
  { label: 'Japanese', value: 'JP' },
  { label: 'French', value: 'FR' },
];

// Types
interface TranslationRequest {
  id: string;
  sourceLanguage: string;
  targetLanguages: string[];
  languagePair: string;
  wordCount: number;
  requestDate: string;
  requestTime: string;
  fileName: string;
  status: string;
  mtModel: string;
  translationStrings?: TranslationString[];
  qualityMetrics?: QualityMetrics[];
}

interface TranslationString {
  id: string;
  sourceText: string;
  translatedText: string;
  targetLanguage: string;
  status: string;
  isApproved: boolean;
  processingTimeMs: number | null;
  annotations?: any[];
}

interface QualityMetrics {
  id: string;
  metricXScore: number | null;
  metricXConfidence: number | null;
  metricXMode: string | null;
  metricXVariant: string | null;
  bleuScore: number | null;
  cometScore: number | null;
  terScore: number | null;
  qualityLabel: string | null;
}

interface TranslationMemory {
  id: string;
  sourceText: string;
  targetText: string;
  sourceLanguage: string;
  targetLanguage: string;
  quality: string;
  domain: string;
  lastUsed: string;
  createdFrom?: string;
  usageCount?: number;
}

interface GlossaryTerm {
  id: string;
  term: string;
  translation: string;
  sourceLanguage: string;
  targetLanguage: string;
  domain: string;
  definition: string;
  usageCount?: number;
}

interface DoNotTranslateItem {
  id: string;
  text: string;
  category: string;
  languages: string[];
  notes: string;
  usageCount?: number;
}

interface OffensiveWord {
  id: string;
  word: string;
  language: string;
  severity: string;
  category: string;
  alternatives?: string[];
  detectionCount?: number;
}

interface FuzzyMatch {
  tm_id: string;
  source_text: string;
  target_text: string;
  similarity: number;
  match_percentage: number;
  domain: string;
  quality: string;
  last_used: string;
}

export const CommandCenter: React.FC = () => {
  const [jobSearchTerm, setJobSearchTerm] = useState('');
  const [targetLanguageFilter, setTargetLanguageFilter] = useState<string[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [sourceLanguageFilter, setSourceLanguageFilter] = useState<string>('all');
  
  const [selectedJob, setSelectedJob] = useState<TranslationRequest | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [activeTab, setActiveTab] = useState('translation-memories');
  const [loading, setLoading] = useState(true);

  // Reference data state
  const [translationRequests, setTranslationRequests] = useState<TranslationRequest[]>([]);
  const [translationMemories, setTranslationMemories] = useState<TranslationMemory[]>([]);
  const [glossaryTerms, setGlossaryTerms] = useState<GlossaryTerm[]>([]);
  const [doNotTranslateItems, setDoNotTranslateItems] = useState<DoNotTranslateItem[]>([]);
  const [offensiveWords, setOffensiveWords] = useState<OffensiveWord[]>([]);

  // Modal states
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<any>(null);

  // Status states for better UX
  const [submitStatus, setSubmitStatus] = useState<{type: 'success' | 'error' | 'idle', message: string}>({type: 'idle', message: ''});

  // Form states for adding new items
  const [newTMForm, setNewTMForm] = useState({
    sourceText: '', targetText: '', sourceLanguage: '', targetLanguage: '', domain: '', quality: 'HIGH'
  });
  const [newGlossaryForm, setNewGlossaryForm] = useState({
    term: '', translation: '', sourceLanguage: '', targetLanguage: '', domain: '', definition: ''
  });
  const [newDNTForm, setNewDNTForm] = useState({
    text: '', category: '', languages: [] as string[], notes: ''
  });
  const [newOffensiveForm, setNewOffensiveForm] = useState({
    word: '', language: '', severity: 'medium', category: '', alternatives: ''
  });

  // File upload ref
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchAllData();
  }, []);

  const getLanguageLabel = (code: string) => {
    return languageOptions.find(lang => lang.value === code)?.label || code;
  };

  const getStatusBadge = (status: string) => {
    const variants = {
      'COMPLETED': 'default',
      'IN_PROGRESS': 'secondary',
      'PENDING': 'outline',
      'FAILED': 'destructive',
      'MULTI_ENGINE_REVIEW': 'secondary'
    } as const;
    
    return (
      <Badge variant={variants[status as keyof typeof variants] || 'outline'}>
        {status.charAt(0).toUpperCase() + status.slice(1).toLowerCase().replace('_', ' ')}
      </Badge>
    );
  };

  // Enhanced Fuzzy Match Display Component
  const FuzzyMatchDisplay: React.FC<{
    sourceText: string;
    sourceLanguage: string;
    targetLanguage: string;
  }> = ({ sourceText, sourceLanguage, targetLanguage }) => {
    const [fuzzyMatches, setFuzzyMatches] = useState<FuzzyMatch[]>([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
      if (sourceText.length > 10) {
        searchFuzzyMatches();
      } else {
        setFuzzyMatches([]);
      }
    }, [sourceText, sourceLanguage, targetLanguage]);

    const searchFuzzyMatches = async () => {
      setLoading(true);
      try {
        const response = await fetch(
          `${API_BASE_URL}/api/translation-memory/fuzzy-matches?` +
          `source_text=${encodeURIComponent(sourceText)}&` +
          `source_language=${sourceLanguage}&` +
          `target_language=${targetLanguage}&` +
          `threshold=0.6`
        );
        
        if (response.ok) {
          const data = await response.json();
          setFuzzyMatches(data.matches);
        }
      } catch (error) {
        console.error('Failed to fetch fuzzy matches:', error);
      } finally {
        setLoading(false);
      }
    };

    const copyToTarget = (targetText: string) => {
      if (activeTab === 'translation-memories') {
        setNewTMForm(prev => ({ ...prev, targetText }));
      }
    };

    if (loading) {
      return (
        <Card className="mt-4">
          <CardContent className="pt-6">
            <div className="text-center text-sm text-muted-foreground">
              Searching for fuzzy matches...
            </div>
          </CardContent>
        </Card>
      );
    }

    if (fuzzyMatches.length === 0) return null;

    return (
      <Card className="mt-4">
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2">
            🔍 Fuzzy Matches Found ({fuzzyMatches.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {fuzzyMatches.map((match, index) => (
              <div key={index} className="p-3 border rounded-md hover:bg-muted/50 transition-colors">
                <div className="flex justify-between items-center mb-2">
                  <Badge variant="outline" className="text-xs">
                    {match.match_percentage}% match
                  </Badge>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary" className="text-xs">{match.quality}</Badge>
                    <Button 
                      size="sm" 
                      variant="ghost" 
                      onClick={() => copyToTarget(match.target_text)}
                      className="h-6 px-2 text-xs"
                    >
                      Use
                    </Button>
                  </div>
                </div>
                <div className="space-y-1">
                  <div className="text-sm"><strong>Source:</strong> {match.source_text}</div>
                  <div className="text-sm"><strong>Target:</strong> {match.target_text}</div>
                  <div className="text-xs text-muted-foreground">
                    Domain: {match.domain} • Last used: {new Date(match.last_used).toLocaleDateString()}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  };

  const getQualityBadge = (quality: string) => {
    const variants = {
      high: 'default',
      medium: 'secondary',
      low: 'destructive'
    } as const;
    
    return (
      <Badge variant={variants[quality as keyof typeof variants] || 'outline'}>
        {quality.charAt(0).toUpperCase() + quality.slice(1)}
      </Badge>
    );
  };

  const getSeverityBadge = (severity: string) => {
    const variants = {
      high: 'destructive',
      medium: 'secondary',
      low: 'outline'
    } as const;
    
    return (
      <Badge variant={variants[severity as keyof typeof variants] || 'outline'}>
        {severity.charAt(0).toUpperCase() + severity.slice(1)}
      </Badge>
    );
  };

  // Status message helper
  const showStatus = (type: 'success' | 'error', message: string) => {
    setSubmitStatus({ type, message });
    setTimeout(() => setSubmitStatus({ type: 'idle', message: '' }), 3000);
  };

  // Fetch all data from backend with error handling
  const fetchAllData = async () => {
    setLoading(true);
    try {
      console.log('Fetching data from:', API_BASE_URL);
      
      // Fetch translation requests
      const requestsResponse = await fetch(`${API_BASE_URL}/api/translation-requests?include=strings,metrics`);
      if (requestsResponse.ok) {
        const requests = await requestsResponse.json();
        console.log('Fetched translation requests:', requests.length);
        setTranslationRequests(requests);
      } else {
        console.error('Failed to fetch translation requests:', requestsResponse.status);
      }

      // Fetch Command Center data from backend
      try {
        const tmResponse = await fetch(`${API_BASE_URL}/api/translation-memory`);
        if (tmResponse.ok) {
          const tmData = await tmResponse.json();
          console.log('Fetched translation memories:', tmData.length);
          setTranslationMemories(tmData);
        }
      } catch (e) {
        console.log("TM endpoint not available, using empty data");
        setTranslationMemories([]);
      }

      try {
        const glossaryResponse = await fetch(`${API_BASE_URL}/api/glossary`);
        if (glossaryResponse.ok) {
          const glossaryData = await glossaryResponse.json();
          console.log('Fetched glossary terms:', glossaryData.length);
          setGlossaryTerms(glossaryData);
        }
      } catch (e) {
        console.log("Glossary endpoint not available, using empty data");
        setGlossaryTerms([]);
      }

      try {
        const dntResponse = await fetch(`${API_BASE_URL}/api/do-not-translate`);
        if (dntResponse.ok) {
          const dntData = await dntResponse.json();
          console.log('Fetched DNT items:', dntData.length);
          setDoNotTranslateItems(dntData);
        }
      } catch (e) {
        console.log("DNT endpoint not available, using empty data");
        setDoNotTranslateItems([]);
      }

      try {
        const offensiveResponse = await fetch(`${API_BASE_URL}/api/offensive-words`);
        if (offensiveResponse.ok) {
          const offensiveData = await offensiveResponse.json();
          console.log('Fetched offensive words:', offensiveData.length);
          setOffensiveWords(offensiveData);
        }
      } catch (e) {
        console.log("Offensive words endpoint not available, using empty data");
        setOffensiveWords([]);
      }

    } catch (error) {
      console.error('Failed to fetch data:', error);
      showStatus('error', 'Failed to fetch data from server');
    } finally {
      setLoading(false);
    }
  };

  // Filter jobs with multiple criteria
  const filteredJobs = useMemo(() => {
    let filtered = translationRequests;
    
    // Filter by target language
    if (targetLanguageFilter.length > 0) {
      filtered = filtered.filter(job => 
        job.targetLanguages.some(lang => targetLanguageFilter.includes(lang))
      );
    }
    
    // Filter by source language
    if (sourceLanguageFilter !== 'all') {
      filtered = filtered.filter(job => job.sourceLanguage === sourceLanguageFilter);
    }
    
    // Filter by status
    if (statusFilter !== 'all') {
      filtered = filtered.filter(job => job.status === statusFilter);
    }
    
    // Filter by search term (filename, language pair, etc.)
    if (jobSearchTerm) {
      filtered = filtered.filter(job =>
        job.fileName.toLowerCase().includes(jobSearchTerm.toLowerCase()) ||
        job.languagePair.toLowerCase().includes(jobSearchTerm.toLowerCase()) ||
        job.mtModel.toLowerCase().includes(jobSearchTerm.toLowerCase())
      );
    }
    
    return filtered;
  }, [translationRequests, targetLanguageFilter, sourceLanguageFilter, statusFilter, jobSearchTerm]);

  // Filter reference data based on search term
  const filterReferenceData = (data: any[], searchFields: string[]) => {
    if (!searchTerm) return data;
    
    return data.filter(item =>
      searchFields.some(field =>
        item[field]?.toLowerCase().includes(searchTerm.toLowerCase())
      )
    );
  };

  const filteredTranslationMemories = filterReferenceData(translationMemories, ['sourceText', 'targetText', 'domain']);
  const filteredGlossaryTerms = filterReferenceData(glossaryTerms, ['term', 'translation', 'domain']);
  const filteredDoNotTranslateItems = filterReferenceData(doNotTranslateItems, ['text', 'category']);
  const filteredOffensiveWords = filterReferenceData(offensiveWords, ['word', 'category']);

  // Add new item functions with UX feedback
  const addTranslationMemory = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/translation-memory`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newTMForm)
      });
      
      if (response.ok) {
        const result = await response.json();
        setTranslationMemories(prev => [...prev, result.data]);
        setNewTMForm({ sourceText: '', targetText: '', sourceLanguage: '', targetLanguage: '', domain: '', quality: 'high' });
        setIsAddModalOpen(false);
        showStatus('success', 'Translation memory saved successfully!');
      } else {
        showStatus('error', 'Failed to save translation memory');
      }
    } catch (error) {
      console.error('Failed to add translation memory:', error);
      showStatus('error', 'Failed to save translation memory');
    }
  };

  const addGlossaryTerm = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/glossary`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newGlossaryForm)
      });
      
      if (response.ok) {
        const result = await response.json();
        setGlossaryTerms(prev => [...prev, result.data]);
        setNewGlossaryForm({ term: '', translation: '', sourceLanguage: '', targetLanguage: '', domain: '', definition: '' });
        setIsAddModalOpen(false);
        showStatus('success', 'Glossary term saved successfully!');
      } else {
        showStatus('error', 'Failed to save glossary term');
      }
    } catch (error) {
      console.error('Failed to add glossary term:', error);
      showStatus('error', 'Failed to save glossary term');
    }
  };

  const addDoNotTranslateItem = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/do-not-translate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newDNTForm)
      });
      
      if (response.ok) {
        const result = await response.json();
        setDoNotTranslateItems(prev => [...prev, result.data]);
        setNewDNTForm({ text: '', category: '', languages: [], notes: '' });
        setIsAddModalOpen(false);
        showStatus('success', 'Do not translate item saved successfully!');
      } else {
        showStatus('error', 'Failed to save do not translate item');
      }
    } catch (error) {
      console.error('Failed to add do not translate item:', error);
      showStatus('error', 'Failed to save do not translate item');
    }
  };

  const addOffensiveWord = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/offensive-words`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newOffensiveForm)
      });
      
      if (response.ok) {
        const result = await response.json();
        setOffensiveWords(prev => [...prev, result.data]);
        setNewOffensiveForm({ word: '', language: '', severity: 'medium', category: '', alternatives: '' });
        setIsAddModalOpen(false);
        showStatus('success', 'Offensive word saved successfully!');
      } else {
        showStatus('error', 'Failed to save offensive word');
      }
    } catch (error) {
      console.error('Failed to add offensive word:', error);
      showStatus('error', 'Failed to save offensive word');
    }
  };

  // Download CSV template functions with proper data
  const downloadTemplate = (type: string) => {
    let csvContent = '';
    let filename = '';

    switch (type) {
      case 'translation-memories':
        csvContent = 'sourceText,targetText,sourceLanguage,targetLanguage,domain,quality\n';
        csvContent += '"Hello","Bonjour","EN","FR","general","high"\n';
        csvContent += '"Good morning","Bon matin","EN","FR","greetings","high"\n';
        csvContent += '"Thank you","Merci","EN","FR","courtesy","medium"\n';
        filename = 'translation_memory_template.csv';
        break;
      case 'glossary':
        csvContent = 'term,translation,sourceLanguage,targetLanguage,domain,definition\n';
        csvContent += '"API","API","EN","FR","technology","Application Programming Interface"\n';
        csvContent += '"Database","Base de données","EN","FR","technology","Structured collection of data"\n';
        csvContent += '"User Interface","Interface utilisateur","EN","FR","technology","Visual elements users interact with"\n';
        filename = 'glossary_template.csv';
        break;
      case 'do-not-translate':
        csvContent = 'text,category,languages,notes\n';
        csvContent += '"NASA","Acronym","EN,FR","Space agency name - keep as is"\n';
        csvContent += '"iPhone","Brand","EN,FR,JP","Apple product name"\n';
        csvContent += '"McDonald\'s","Brand","EN,FR,JP","Restaurant chain name"\n';
        filename = 'do_not_translate_template.csv';
        break;
      case 'offensive-words':
        csvContent = 'word,language,severity,category,alternatives\n';
        csvContent += '"inappropriate","EN","high","profanity","unsuitable,improper"\n';
        csvContent += '"offensive","EN","medium","inappropriate","objectionable,unacceptable"\n';
        filename = 'offensive_words_template.csv';
        break;
    }

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  };

  // Upload CSV function
  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('type', activeTab);

    try {
      const response = await fetch(`${API_BASE_URL}/api/bulk-upload`, {
        method: 'POST',
        body: formData
      });

      if (response.ok) {
        await fetchAllData();
        setIsUploadModalOpen(false);
        showStatus('success', 'File uploaded successfully!');
      } else {
        showStatus('error', 'Upload failed. Please check your file format.');
      }
    } catch (error) {
      console.error('Upload failed:', error);
      showStatus('error', 'Upload failed. Please try again.');
    }

    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Download translation job CSV
  const downloadJobCSV = (job: TranslationRequest) => {
    if (!job.translationStrings) return;

    let csvContent = 'sourceText,translatedText,sourceLanguage,targetLanguage,status,isApproved\n';
    
    job.translationStrings.forEach(string => {
      const row = [
        `"${string.sourceText.replace(/"/g, '""')}"`,
        `"${string.translatedText.replace(/"/g, '""')}"`,
        job.sourceLanguage,
        string.targetLanguage,
        string.status,
        string.isApproved
      ].join(',');
      csvContent += row + '\n';
    });

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `translation_job_${job.id}_${job.fileName}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  };

  // Delete item function with UX feedback
  const deleteItem = async (id: string, type: string) => {
    if (!confirm('Are you sure you want to delete this item?')) return;

    try {
      let endpoint = '';
      switch (type) {
        case 'translation-memories':
          endpoint = `/api/translation-memory/${id}`;
          break;
        case 'glossary':
          endpoint = `/api/glossary/${id}`;
          break;
        case 'do-not-translate':
          endpoint = `/api/do-not-translate/${id}`;
          break;
        case 'offensive-words':
          endpoint = `/api/offensive-words/${id}`;
          break;
      }

      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        // Update local state
        switch (type) {
          case 'translation-memories':
            setTranslationMemories(prev => prev.filter(item => item.id !== id));
            break;
          case 'glossary':
            setGlossaryTerms(prev => prev.filter(item => item.id !== id));
            break;
          case 'do-not-translate':
            setDoNotTranslateItems(prev => prev.filter(item => item.id !== id));
            break;
          case 'offensive-words':
            setOffensiveWords(prev => prev.filter(item => item.id !== id));
            break;
        }
        showStatus('success', 'Item deleted successfully!');
      } else {
        showStatus('error', 'Failed to delete item');
      }
    } catch (error) {
      console.error('Failed to delete item:', error);
      showStatus('error', 'Failed to delete item');
    }
  };

  // Render add modal content based on active tab
  const renderAddModalContent = () => {
    switch (activeTab) {
      case 'translation-memories':
        return (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Source Text</Label>
                <Textarea
                  value={newTMForm.sourceText}
                  onChange={(e) => setNewTMForm({...newTMForm, sourceText: e.target.value})}
                  placeholder="Enter source text"
                />
              </div>
              <div>
                <Label>Target Text</Label>
                <Textarea
                  value={newTMForm.targetText}
                  onChange={(e) => setNewTMForm({...newTMForm, targetText: e.target.value})}
                  placeholder="Enter target text"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Source Language</Label>
                <Select value={newTMForm.sourceLanguage} onValueChange={(value) => setNewTMForm({...newTMForm, sourceLanguage: value})}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select source language" />
                  </SelectTrigger>
                  <SelectContent>
                    {languageOptions.map(lang => (
                      <SelectItem key={lang.value} value={lang.value}>{lang.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Target Language</Label>
                <Select value={newTMForm.targetLanguage} onValueChange={(value) => setNewTMForm({...newTMForm, targetLanguage: value})}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select target language" />
                  </SelectTrigger>
                  <SelectContent>
                    {languageOptions.map(lang => (
                      <SelectItem key={lang.value} value={lang.value}>{lang.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Domain</Label>
                <Input
                  value={newTMForm.domain}
                  onChange={(e) => setNewTMForm({...newTMForm, domain: e.target.value})}
                  placeholder="e.g., technology, medical"
                />
              </div>
              <div>
                <Label>Quality</Label>
                <Select value={newTMForm.quality} onValueChange={(value) => setNewTMForm({...newTMForm, quality: value})}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="HIGH">High</SelectItem>
                    <SelectItem value="MEDIUM">Medium</SelectItem>
                    <SelectItem value="LOW">Low</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            
            {/* Show fuzzy matches when typing */}
            {newTMForm.sourceText && newTMForm.sourceLanguage && newTMForm.targetLanguage && (
              <FuzzyMatchDisplay
                sourceText={newTMForm.sourceText}
                sourceLanguage={newTMForm.sourceLanguage}
                targetLanguage={newTMForm.targetLanguage}
              />
            )}
            
            <Button onClick={addTranslationMemory} className="w-full">Add Translation Memory</Button>
          </div>
        );

      case 'glossary':
        return (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Term</Label>
                <Input
                  value={newGlossaryForm.term}
                  onChange={(e) => setNewGlossaryForm({...newGlossaryForm, term: e.target.value})}
                  placeholder="Enter term"
                />
              </div>
              <div>
                <Label>Translation</Label>
                <Input
                  value={newGlossaryForm.translation}
                  onChange={(e) => setNewGlossaryForm({...newGlossaryForm, translation: e.target.value})}
                  placeholder="Enter translation"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Source Language</Label>
                <Select value={newGlossaryForm.sourceLanguage} onValueChange={(value) => setNewGlossaryForm({...newGlossaryForm, sourceLanguage: value})}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select source language" />
                  </SelectTrigger>
                  <SelectContent>
                    {languageOptions.map(lang => (
                      <SelectItem key={lang.value} value={lang.value}>{lang.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Target Language</Label>
                <Select value={newGlossaryForm.targetLanguage} onValueChange={(value) => setNewGlossaryForm({...newGlossaryForm, targetLanguage: value})}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select target language" />
                  </SelectTrigger>
                  <SelectContent>
                    {languageOptions.map(lang => (
                      <SelectItem key={lang.value} value={lang.value}>{lang.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <Label>Domain</Label>
              <Input
                value={newGlossaryForm.domain}
                onChange={(e) => setNewGlossaryForm({...newGlossaryForm, domain: e.target.value})}
                placeholder="e.g., technology, medical"
              />
            </div>
            <div>
              <Label>Definition</Label>
              <Textarea
                value={newGlossaryForm.definition}
                onChange={(e) => setNewGlossaryForm({...newGlossaryForm, definition: e.target.value})}
                placeholder="Enter definition"
              />
            </div>
            <Button onClick={addGlossaryTerm} className="w-full">Add Glossary Term</Button>
          </div>
        );

      case 'do-not-translate':
        return (
          <div className="space-y-4">
            <div>
              <Label>Text</Label>
              <Input
                value={newDNTForm.text}
                onChange={(e) => setNewDNTForm({...newDNTForm, text: e.target.value})}
                placeholder="Enter text that should not be translated"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Category</Label>
                <Input
                  value={newDNTForm.category}
                  onChange={(e) => setNewDNTForm({...newDNTForm, category: e.target.value})}
                  placeholder="e.g., Brand, Acronym, Proper Noun"
                />
              </div>
              <div>
                <Label>Languages</Label>
                <MultiSelect
                  options={languageOptions}
                  selectedValues={newDNTForm.languages}
                  onSelectionChange={(values) => setNewDNTForm({...newDNTForm, languages: values})}
                  placeholder="Select languages"
                />
              </div>
            </div>
            <div>
              <Label>Notes</Label>
              <Textarea
                value={newDNTForm.notes}
                onChange={(e) => setNewDNTForm({...newDNTForm, notes: e.target.value})}
                placeholder="Additional notes"
              />
            </div>
            <Button onClick={addDoNotTranslateItem} className="w-full">Add Do Not Translate Item</Button>
          </div>
        );

      case 'offensive-words':
        return (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Word</Label>
                <Input
                  value={newOffensiveForm.word}
                  onChange={(e) => setNewOffensiveForm({...newOffensiveForm, word: e.target.value})}
                  placeholder="Enter offensive word"
                />
              </div>
              <div>
                <Label>Language</Label>
                <Select value={newOffensiveForm.language} onValueChange={(value) => setNewOffensiveForm({...newOffensiveForm, language: value})}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select language" />
                  </SelectTrigger>
                  <SelectContent>
                    {languageOptions.map(lang => (
                      <SelectItem key={lang.value} value={lang.value}>{lang.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Severity</Label>
                <Select value={newOffensiveForm.severity} onValueChange={(value) => setNewOffensiveForm({...newOffensiveForm, severity: value})}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="high">High</SelectItem>
                    <SelectItem value="medium">Medium</SelectItem>
                    <SelectItem value="low">Low</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Category</Label>
                <Input
                  value={newOffensiveForm.category}
                  onChange={(e) => setNewOffensiveForm({...newOffensiveForm, category: e.target.value})}
                  placeholder="e.g., profanity, hate speech"
                />
              </div>
            </div>
            <div>
              <Label>Alternatives (comma-separated)</Label>
              <Input
                value={newOffensiveForm.alternatives}
                onChange={(e) => setNewOffensiveForm({...newOffensiveForm, alternatives: e.target.value})}
                placeholder="alternative1, alternative2"
              />
            </div>
            <Button onClick={addOffensiveWord} className="w-full">Add Offensive Word</Button>
          </div>
        );

      default:
        return null;
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold">Command Center</h1>
        </div>
        <Card>
          <CardContent className="text-center py-8">
            <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-4" />
            <p>Loading command center data...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Command Center</h1>
        <Button onClick={fetchAllData} variant="outline">
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Status Message */}
      {submitStatus.type !== 'idle' && (
        <div className={`p-3 rounded-md text-sm flex items-center gap-2 ${
          submitStatus.type === 'success' 
            ? 'bg-green-50 text-green-800 border border-green-200' 
            : 'bg-red-50 text-red-800 border border-red-200'
        }`}>
          {submitStatus.type === 'success' ? <CheckCircle className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
          {submitStatus.message}
        </div>
      )}

      {/* CHANGE 1: Reference Data Tables moved to top */}
      <Card>
        <CardHeader>
          <CardTitle>Reference Data Management</CardTitle>
          <div className="flex items-center space-x-4">
            <div className="flex-1 max-w-md">
              <Input
                placeholder="Search reference data..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <div className="flex space-x-2">
              <Dialog open={isAddModalOpen} onOpenChange={setIsAddModalOpen}>
                <DialogTrigger asChild>
                  <Button>
                    <Plus className="h-4 w-4 mr-2" />
                    Add New Entry
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-w-2xl">
                  <DialogHeader>
                    <DialogTitle>Add New {activeTab.replace('-', ' ').replace(/\b\w/g, l => l.toUpperCase())} Entry</DialogTitle>
                  </DialogHeader>
                  {renderAddModalContent()}
                </DialogContent>
              </Dialog>

              <Button variant="outline" onClick={() => downloadTemplate(activeTab)}>
                <FileDown className="h-4 w-4 mr-2" />
                Download Template
              </Button>

              <Dialog open={isUploadModalOpen} onOpenChange={setIsUploadModalOpen}>
                <DialogTrigger asChild>
                  <Button variant="outline">
                    <Upload className="h-4 w-4 mr-2" />
                    Bulk Upload
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Bulk Upload {activeTab.replace('-', ' ').replace(/\b\w/g, l => l.toUpperCase())}</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4">
                    <p className="text-sm text-muted-foreground">
                      Upload a CSV file to add multiple entries. The upload will append to existing data, not overwrite it.
                    </p>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".csv"
                      onChange={handleFileUpload}
                      className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                    />
                  </div>
                </DialogContent>
              </Dialog>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="translation-memories">Translation Memories</TabsTrigger>
              <TabsTrigger value="glossary">Glossary</TabsTrigger>
              <TabsTrigger value="do-not-translate">Do Not Translate</TabsTrigger>
              <TabsTrigger value="offensive-words">Offensive Words</TabsTrigger>
            </TabsList>

            {/* Translation Memories Tab */}
            <TabsContent value="translation-memories">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Source Text</TableHead>
                    <TableHead>Target Text</TableHead>
                    <TableHead>Languages</TableHead>
                    <TableHead>Quality</TableHead>
                    <TableHead>Domain</TableHead>
                    <TableHead>Last Used</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead>Usage</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredTranslationMemories.map((memory) => (
                    <TableRow key={memory.id}>
                      <TableCell className="max-w-xs truncate">{memory.sourceText}</TableCell>
                      <TableCell className="max-w-xs truncate">{memory.targetText}</TableCell>
                      <TableCell>
                        <div className="flex space-x-1">
                          <Badge variant="outline" className="text-xs">
                            {getLanguageLabel(memory.sourceLanguage)}
                          </Badge>
                          <span>→</span>
                          <Badge variant="secondary" className="text-xs">
                            {getLanguageLabel(memory.targetLanguage)}
                          </Badge>
                        </div>
                      </TableCell>
                      <TableCell>{getQualityBadge(memory.quality)}</TableCell>
                      <TableCell>{memory.domain}</TableCell>
                      <TableCell>{new Date(memory.lastUsed).toLocaleDateString()}</TableCell>
                      <TableCell>
                        {memory.createdFrom && memory.createdFrom.startsWith('qa_approval') ? (
                          <Badge variant="secondary" className="text-xs">QA Approved</Badge>
                        ) : (
                          <Badge variant="outline" className="text-xs">Manual</Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <span className="text-xs text-muted-foreground">
                          {memory.usageCount || 0} uses
                        </span>
                      </TableCell>
                      <TableCell>
                        <div className="flex space-x-1">
                          <Button size="sm" variant="outline">
                            <Edit className="h-3 w-3" />
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => deleteItem(memory.id, 'translation-memories')}>
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TabsContent>

            {/* Glossary Tab */}
            <TabsContent value="glossary">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Term</TableHead>
                    <TableHead>Translation</TableHead>
                    <TableHead>Languages</TableHead>
                    <TableHead>Domain</TableHead>
                    <TableHead>Definition</TableHead>
                    <TableHead>Usage</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredGlossaryTerms.map((term) => (
                    <TableRow key={term.id}>
                      <TableCell className="font-medium">{term.term}</TableCell>
                      <TableCell>{term.translation}</TableCell>
                      <TableCell>
                        <div className="flex space-x-1">
                          <Badge variant="outline" className="text-xs">
                            {getLanguageLabel(term.sourceLanguage)}
                          </Badge>
                          <span>→</span>
                          <Badge variant="secondary" className="text-xs">
                            {getLanguageLabel(term.targetLanguage)}
                          </Badge>
                        </div>
                      </TableCell>
                      <TableCell>{term.domain}</TableCell>
                      <TableCell className="max-w-xs truncate">{term.definition}</TableCell>
                      <TableCell>
                        <span className="text-xs text-muted-foreground">
                          {term.usageCount || 0} uses
                        </span>
                      </TableCell>
                      <TableCell>
                        <div className="flex space-x-1">
                          <Button size="sm" variant="outline">
                            <Edit className="h-3 w-3" />
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => deleteItem(term.id, 'glossary')}>
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TabsContent>

            {/* Do Not Translate Tab */}
            <TabsContent value="do-not-translate">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Text</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>Languages</TableHead>
                    <TableHead>Notes</TableHead>
                    <TableHead>Usage</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredDoNotTranslateItems.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell className="font-medium">{item.text}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{item.category}</Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {item.languages.map((lang, index) => (
                            <Badge key={index} variant="secondary" className="text-xs">
                              {getLanguageLabel(lang)}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell className="max-w-xs truncate">{item.notes}</TableCell>
                      <TableCell>
                        <span className="text-xs text-muted-foreground">
                          {item.usageCount || 0} uses
                        </span>
                      </TableCell>
                      <TableCell>
                        <div className="flex space-x-1">
                          <Button size="sm" variant="outline">
                            <Edit className="h-3 w-3" />
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => deleteItem(item.id, 'do-not-translate')}>
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TabsContent>

            {/* Offensive Words Tab */}
            <TabsContent value="offensive-words">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Word</TableHead>
                    <TableHead>Language</TableHead>
                    <TableHead>Severity</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>Alternatives</TableHead>
                    <TableHead>Detections</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredOffensiveWords.map((word) => (
                    <TableRow key={word.id}>
                      <TableCell className="font-medium">
                        <div className="flex items-center space-x-2">
                          <AlertTriangle className="h-4 w-4 text-red-500" />
                          <span>{word.word}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">
                          {getLanguageLabel(word.language)}
                        </Badge>
                      </TableCell>
                      <TableCell>{getSeverityBadge(word.severity)}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{word.category}</Badge>
                      </TableCell>
                      <TableCell className="max-w-xs truncate">
                        {word.alternatives?.join(', ')}
                      </TableCell>
                      <TableCell>
                        <span className="text-xs text-muted-foreground">
                          {word.detectionCount || 0} times
                        </span>
                      </TableCell>
                      <TableCell>
                        <div className="flex space-x-1">
                          <Button size="sm" variant="outline">
                            <Edit className="h-3 w-3" />
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => deleteItem(word.id, 'offensive-words')}>
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* CHANGE 2: Translation Jobs Table with integrated filters */}
      <Card>
        <CardHeader>
          <CardTitle>Translation Jobs Overview</CardTitle>
          {/* CHANGE 2: Moved filters inside the table card */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mt-4">
            <div>
              <Label className="text-sm font-medium">Search Jobs</Label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search filename, model..."
                  value={jobSearchTerm}
                  onChange={(e) => setJobSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>
            <div>
              <Label className="text-sm font-medium">Source Language</Label>
              <Select value={sourceLanguageFilter} onValueChange={setSourceLanguageFilter}>
                <SelectTrigger>
                  <SelectValue placeholder="All sources" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Sources</SelectItem>
                  {languageOptions.map(lang => (
                    <SelectItem key={lang.value} value={lang.value}>{lang.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-sm font-medium">Target Languages</Label>
              <MultiSelect
                options={languageOptions}
                selectedValues={targetLanguageFilter}
                onSelectionChange={setTargetLanguageFilter}
                placeholder="All targets"
              />
            </div>
            <div>
              <Label className="text-sm font-medium">Status</Label>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger>
                  <SelectValue placeholder="All statuses" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Statuses</SelectItem>
                  <SelectItem value="COMPLETED">Completed</SelectItem>
                  <SelectItem value="IN_PROGRESS">In Progress</SelectItem>
                  <SelectItem value="PENDING">Pending</SelectItem>
                  <SelectItem value="MULTI_ENGINE_REVIEW">Multi-Engine Review</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="text-sm text-muted-foreground mt-2">
            Showing {filteredJobs.length} of {translationRequests.length} jobs
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Submission Date</TableHead>
                <TableHead>Submission Time</TableHead>
                <TableHead>Source Language</TableHead>
                <TableHead>Target Languages</TableHead>
                <TableHead>File Name</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Strings</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredJobs.map((job) => (
                <TableRow 
                  key={job.id}
                  className={selectedJob?.id === job.id ? 'bg-muted/50' : ''}
                >
                  <TableCell>{new Date(job.requestDate).toLocaleDateString()}</TableCell>
                  <TableCell>{new Date(job.requestTime).toLocaleTimeString()}</TableCell>
                  <TableCell>
                    <Badge variant="outline">
                      {getLanguageLabel(job.sourceLanguage)}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {job.targetLanguages.map((lang, index) => (
                        <Badge key={index} variant="secondary" className="text-xs">
                          {getLanguageLabel(lang)}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="font-mono text-sm">{job.fileName}</TableCell>
                  <TableCell>{getStatusBadge(job.status)}</TableCell>
                  <TableCell>
                    <span className="font-semibold">{job.translationStrings?.length || 0}</span>
                    <span className="text-xs text-muted-foreground ml-1">strings</span>
                  </TableCell>
                  <TableCell>
                    <div className="flex space-x-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setSelectedJob(job)}
                      >
                        Select
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => downloadJobCSV(job)}
                        disabled={!job.translationStrings || job.translationStrings.length === 0}
                      >
                        <Download className="h-3 w-3 mr-1" />
                        Download
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Selected Job Details */}
      {selectedJob && (
        <Card>
          <CardHeader>
            <CardTitle>Selected Job Details</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <strong>File:</strong> {selectedJob.fileName}
              </div>
              <div>
                <strong>Status:</strong> {getStatusBadge(selectedJob.status)}
              </div>
              <div>
                <strong>Source Language:</strong> {getLanguageLabel(selectedJob.sourceLanguage)}
              </div>
              <div>
                <strong>Target Languages:</strong> {selectedJob.targetLanguages.map(lang => getLanguageLabel(lang)).join(', ')}
              </div>
              <div>
                <strong>Word Count:</strong> {selectedJob.wordCount.toLocaleString()} {selectedJob.sourceLanguage === 'JP' ? 'characters' : 'words'}
              </div>
              <div>
                <strong>Translation Strings:</strong> {selectedJob.translationStrings?.length || 0}
              </div>
              {selectedJob.qualityMetrics && selectedJob.qualityMetrics.length > 0 && (
                <>
                  <div>
                    <strong>MetricX Score:</strong> {selectedJob.qualityMetrics[0].metricXScore?.toFixed(1) || 'N/A'}
                  </div>
                  <div>
                    <strong>BLEU Score:</strong> {selectedJob.qualityMetrics[0].bleuScore ? (selectedJob.qualityMetrics[0].bleuScore * 100).toFixed(1) + '%' : 'N/A'}
                  </div>
                </>
              )}
            </div>
            <div className="mt-4 flex space-x-2">
              <Button variant="outline" onClick={() => setSelectedJob(null)}>
                Clear Selection
              </Button>
              {selectedJob.translationStrings && selectedJob.translationStrings.length > 0 && (
                <Button variant="outline" onClick={() => downloadJobCSV(selectedJob)}>
                  <Download className="h-4 w-4 mr-2" />
                  Download CSV
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default CommandCenter;
