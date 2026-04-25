"use client"

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { BarChart3, CheckCircle, ChevronLeft, ChevronRight, Copy, Loader2, MessageSquare, PartyPopper, Wand2, X, XCircle } from 'lucide-react';
import React, { useEffect, useState } from 'react';

const API_BASE_URL = 'http://localhost:8001';

interface TranslationString {
  id: string;
  sourceText: string;
  translatedText: string;
  referenceText?: string;
  targetLanguage: string;
  status: string;
  isApproved: boolean;
  annotations: Annotation[];
  qualityMetrics?: QualityMetrics;
  processingTimeMs?: number;
  rlhfSubmitted?: boolean;
  engineResults?: EngineResult[];
  selectedEngine?: string;
  enginePreferences?: any[];
  fuzzyMatches?: any[];
  suggestedTranslation?: string;
}

interface Annotation {
  id: string;
  category: string;
  severity: string;
  comment: string;
  reviewer?: string;
  timestamp: string;
}

interface QualityMetrics {
  bleuScore?: number;
  cometScore?: number;
  terScore?: number;
  cometKiwiScore?: number;
  qualityLabel?: string;
  hasReference?: boolean;
  referenceType?: string;
}

interface TranslationRequest {
  id: string;
  sourceLanguage: string;
  targetLanguages: string[];
  fileName: string;
  status: string;
  translationStrings: TranslationString[];
  qualityMetrics: QualityMetrics[];
  requestDate: string;
  wordCount: number;
  requestType?: string;
  advertiserProfileId?: string;
}

interface AgentEvent {
  type: 'narrate' | 'iteration' | 'done' | 'error';
  message?: string;
  attempt?: number;
  brand_voice_before?: number;
  brand_voice_after?: number;
  cultural_fitness_after?: number;
  feedback?: string;
  text?: string;
  final_score?: number;
  iterations?: number;
  was_improved?: boolean;
  final_text?: string;
}

interface RefineState {
  streaming: boolean;
  events: AgentEvent[];
  done: boolean;
  finalScore?: number;
  wasImproved?: boolean;
}

interface EngineResult {
  engine: string;
  text: string;
  confidence: number;
  processing_time: number;
  error?: string;
  model?: string;
}

const getEngineDisplayName = (engine: string) => {
  const names: { [key: string]: string } = {
    'opus_fast': 'OPUS Fast',
    'elan_specialist': 'ELAN Specialist',
    'elan_quality': 'ELAN Quality',
    'mt5_multilingual': 'mT5 Multilingual',
    'opus_enhanced': 'OPUS Enhanced',
    't5_versatile': 'mT5 Versatile',
    'nllb_multilingual': 'NLLB Multilingual',
  };
  return names[engine] || engine;
};

const getEngineIcon = (engine: string) => {
  const icons: { [key: string]: string } = {
    'opus_fast': '⚡',
    'elan_specialist': '🎯',
    'mt5_multilingual': '🌐',
    'opus_enhanced': '⭐',
    'elan_quality': '🎯', 
    't5_versatile': '🤖',
    'nllb_multilingual': '🌍',
  };
  return icons[engine] || '⚙️'; // Default icon
};

const ModelOutputCard: React.FC<{
  result: EngineResult;
  translationStringId: string;
  sourceLanguage: string;
  targetLanguage: string;
  onCopyToEditor: (text: string) => void;
  onRatingSubmit: (rating: number, annotations: any[]) => void;
  onAnnotationAdd: (annotation: any) => void;
}> = ({ result, translationStringId, sourceLanguage, targetLanguage, onCopyToEditor, onRatingSubmit, onAnnotationAdd }) => {
  const [rating, setRating] = useState(3);
  const [annotations, setAnnotations] = useState('');
  const [newAnnotation, setNewAnnotation] = useState({
    category: '',
    severity: '',
    comment: ''
  });
  const [showCopySuccess, setShowCopySuccess] = useState(false);

  const handleCopy = async () => {
    try {
        await navigator.clipboard.writeText(result.text);

        // FIX: Add '/translation-requests' to the path for select-engine
        await fetch(`${API_BASE_URL}/api/translation-requests/translation-strings/${translationStringId}/select-engine`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                engine: result.engine,
                rating: 3, // Default rating
                comments: "Selected via copy button"
            })
        });

        // FIX: Add '/translation-requests' to the path for translation-preferences
        await fetch(`${API_BASE_URL}/api/translation-requests/translation-preferences`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                translationStringId,
                selectedEngine: result.engine,
                selectionMethod: 'COPY_BUTTON',
                sourceLanguage,
                targetLanguage
            })
        });

        onCopyToEditor(result.text);
        setShowCopySuccess(true);
        setTimeout(() => setShowCopySuccess(false), 2000);
    } catch (error) {
        console.error('Failed to copy or track preference:', error);
    }
};
  const handleRatingSubmit = async () => {
    const annotationList = annotations.trim() ?
      [{ category: 'general', comment: annotations, severity: 'minor' }] : [];

    await fetch(`${API_BASE_URL}/api/analytics/rlhf/quality-rating`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        translationStringId,
        qualityScore: rating,
        annotations: annotationList
      })
    });

    onRatingSubmit(rating, annotationList);
    setAnnotations('');
  };

  const handleAnnotationSubmit = async () => { 
    if (newAnnotation.category && newAnnotation.comment && translationStringId) {
      try {        
        await fetch(`${API_BASE_URL}/api/translation-requests/translation-strings/${translationStringId}/annotations`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(newAnnotation)
        });
        onAnnotationAdd(newAnnotation);
        setNewAnnotation({ category: '', severity: '', comment: '' });
      } catch (error) {
        console.error('Failed to add annotation:', error);
      }
    }
  };

  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm flex items-center gap-2">
          {getEngineIcon(result.engine)}
          {getEngineDisplayName(result.engine)}
          {result.model && (
            <Badge variant="outline" className="text-xs">
              {result.model}
            </Badge>
          )}
          <Badge variant="secondary" className="text-xs ml-auto">
            {result.processing_time?.toFixed(0)}ms
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {result.error ? (
          <div className="text-destructive text-sm p-2 bg-destructive/10 rounded border border-destructive/20">
            Error: {result.error}
          </div>
        ) : (
          <div className="text-sm p-3 bg-muted rounded border">
            {result.text}
          </div>
        )}

        <div className="text-xs text-muted-foreground">
          Engine self-score: {(result.confidence * 100).toFixed(0)}%
        </div>

        <Button
          onClick={handleCopy}
          size="sm"
          className="w-full"
          variant={showCopySuccess ? "default" : "outline"}
        >
          <Copy className="w-4 h-4 mr-2" />
          {showCopySuccess ? "Copied to Editor!" : "Copy to Editor"}
        </Button>

        <div className="space-y-2">
          <Label className="text-xs">Rate Quality (1-5)</Label>
          <Select value={rating.toString()} onValueChange={(value) => setRating(parseInt(value))}>
            <SelectTrigger className="h-8">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1">1 - Very Poor</SelectItem>
              <SelectItem value="2">2 - Poor</SelectItem>
              <SelectItem value="3">3 - Fair</SelectItem>
              <SelectItem value="4">4 - Good</SelectItem>
              <SelectItem value="5">5 - Excellent</SelectItem>
            </SelectContent>
          </Select>
          <Textarea
            value={annotations}
            onChange={(e) => setAnnotations(e.target.value)}
            placeholder="Comments..."
            rows={2}
            className="text-xs resize-none"
          />
          <Button onClick={handleRatingSubmit} size="sm" className="w-full">
            Submit Rating
          </Button>
        </div>

        <div className="space-y-2">
          <Label className="text-xs">Add Annotation</Label>
          <Select
            value={newAnnotation.category}
            onValueChange={(value) => setNewAnnotation({...newAnnotation, category: value})}
          >
            <SelectTrigger className="h-8">
              <SelectValue placeholder="Category" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="accuracy">Accuracy</SelectItem>
              <SelectItem value="fluency">Fluency</SelectItem>
              <SelectItem value="terminology">Terminology</SelectItem>
              <SelectItem value="style">Style</SelectItem>
              <SelectItem value="grammar">Grammar</SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={newAnnotation.severity}
            onValueChange={(value) => setNewAnnotation({...newAnnotation, severity: value})}
          >
            <SelectTrigger className="h-8">
              <SelectValue placeholder="Severity" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="minor">Minor</SelectItem>
              <SelectItem value="major">Major</SelectItem>
              <SelectItem value="critical">Critical</SelectItem>
            </SelectContent>
          </Select>
          <Textarea
            value={newAnnotation.comment}
            onChange={(e) => setNewAnnotation({...newAnnotation, comment: e.target.value})}
            placeholder="Comment..."
            rows={2}
            className="text-xs resize-none"
          />
          <Button onClick={handleAnnotationSubmit} size="sm" className="w-full">
            Add Annotation
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

const TMMatchesCard: React.FC<{
  fuzzyMatches: any[];
  onCopyToEditor: (text: string) => void;
}> = ({ fuzzyMatches, onCopyToEditor }) => {
  if (fuzzyMatches.length === 0) return null;

  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm flex items-center gap-2">
          🔍 Translation Memory ({fuzzyMatches.length})
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {(Array.isArray(fuzzyMatches) ? fuzzyMatches : []).map((match: any, index: number) => (
          <div key={index} className="border rounded p-3 space-y-2">
            <div className="flex justify-between items-center">
              <Badge variant="secondary">{match.match_percentage}% match</Badge>
              <Badge variant="outline">{match.quality}</Badge>
            </div>
            <div className="text-xs space-y-1">
              <div><strong>Source:</strong> {match.source_text}</div>
              <div><strong>Target:</strong> {match.target_text}</div>
              <div className="text-muted-foreground">
                Domain: {match.domain} • Last used: {new Date(match.last_used).toLocaleDateString()}
              </div>
            </div>
            <Button
              onClick={() => onCopyToEditor(match.target_text)}
              className="w-full"
              size="sm"
            >
              Copy to Editor
            </Button>
          </div>
        ))}
      </CardContent>
    </Card>
  );
};

const BulkReviewOverlay: React.FC<{
  selectedString: TranslationString;
  editedText: string;
  setEditedText: (text: string) => void;
  selectedStatus: string;
  setSelectedStatus: (status: string) => void;
  onClose: () => void;
  onContinueReviewing: () => void;
  onUpdate: () => void;
  onApprove: () => void;
  onNext: () => void;
  onPrevious: () => void;
  currentIndex: number;
  totalCount: number;
  approvedCount: number;
  reviewComplete: boolean;
  onQualityRating: (rating: number, annotations: any[]) => void;
  onAnnotationAdd: (annotation: any) => void;
  selectedRequest: TranslationRequest | null;
  stringConfidence?: { confidence: number | null; n_signals: number; mean_quality: number | null };
  onRefine: (stringId: string) => void;
  refineState: Record<string, RefineState>;
}> = ({
  selectedString,
  editedText,
  setEditedText,
  selectedStatus,
  setSelectedStatus,
  onClose,
  onContinueReviewing,
  onUpdate,
  onApprove,
  onNext,
  onPrevious,
  currentIndex,
  totalCount,
  approvedCount,
  reviewComplete,
  onQualityRating,
  onAnnotationAdd,
  selectedRequest,
  stringConfidence,
  onRefine,
  refineState,
}) => {
  const engineResults = selectedString.engineResults || [];
  const fuzzyMatches = selectedString.fuzzyMatches || [];

  const [saveFeedback, setSaveFeedback] = useState(false);
  const [approveFeedback, setApproveFeedback] = useState(false);

  // Translator details state
  const [reviewerExpertise, setReviewerExpertise] = useState('');
  const [approvalType, setApprovalType] = useState('');
  const [cognitiveLoad, setCognitiveLoad] = useState(3);
  const [domainFamiliarity, setDomainFamiliarity] = useState(3);

  const handleCopyToEditor = (text: string) => {
    setEditedText(text);
  };

  const handleUpdate = () => {
    setSaveFeedback(true);
    setTimeout(() => setSaveFeedback(false), 1500);
    onUpdate();
  };

  const handleApprove = () => {
    setApproveFeedback(true);
    setTimeout(() => setApproveFeedback(false), 1500);
    onApprove();
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-background rounded-lg shadow-xl w-full max-w-7xl h-[90vh] flex flex-col border">
        <div className="flex justify-between items-center p-6 border-b bg-muted/30">
          <h2 className="text-xl font-semibold">Bulk Review Mode</h2>
          <div className="flex items-center gap-4">
            {reviewComplete ? (
              <span className="text-sm font-medium text-green-500">All strings reviewed</span>
            ) : (
              <span className="text-sm text-muted-foreground">
                {currentIndex + 1} / {totalCount}
              </span>
            )}
            {stringConfidence && !reviewComplete && (() => {
              const { confidence, n_signals } = stringConfidence;
              if (confidence === null || n_signals < 2) {
                return <Badge variant="outline" className="text-xs text-muted-foreground">Signal confidence: —</Badge>;
              }
              const pct = Math.round(confidence * 100);
              if (confidence >= 0.7) {
                return <Badge variant="outline" className="text-xs border-green-500 text-green-600 dark:text-green-400">Signal confidence: {pct}%</Badge>;
              } else if (confidence >= 0.4) {
                return <Badge variant="outline" className="text-xs border-yellow-500 text-yellow-600 dark:text-yellow-400">Signal confidence: {pct}%</Badge>;
              } else {
                return <Badge variant="outline" className="text-xs border-red-500 text-red-600 dark:text-red-400">Signal confidence: {pct}%</Badge>;
              }
            })()}
            <Button onClick={onClose} variant="outline" size="sm">
              <X className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {reviewComplete ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-6 p-8 text-center">
            <PartyPopper className="h-16 w-16 text-green-500" />
            <div>
              <h3 className="text-2xl font-semibold mb-2">Review Complete</h3>
              <p className="text-muted-foreground text-lg">
                You reviewed all {totalCount} string{totalCount !== 1 ? 's' : ''} in this job.
              </p>
              <p className="text-muted-foreground mt-1">
                <span className="font-medium text-green-500">{approvedCount}</span> approved
                {totalCount - approvedCount > 0 && (
                  <span> · <span className="font-medium text-yellow-500">{totalCount - approvedCount}</span> pending</span>
                )}
              </p>
            </div>
            <div className="flex gap-3">
              <Button onClick={onContinueReviewing} variant="outline" size="lg">
                Continue Reviewing
              </Button>
              <Button onClick={onClose} size="lg">
                <CheckCircle className="w-5 h-5 mr-2" />
                Close
              </Button>
            </div>
          </div>
        ) : (
        <>
        <div className="flex-1 overflow-auto p-6 space-y-6">
          {/* Layout change: Source Text and Translation Editor side-by-side */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6"> {/* Added grid layout */}
            {/* 1. Source Text Card */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Source Text</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-sm p-3 bg-muted rounded border">
                  {selectedString.sourceText}
                </div>
              </CardContent>
            </Card>

            {/* 2. Translation Editor Card */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Translation Editor</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label htmlFor="translation-editor">MT Translation (Editable)</Label>
                  <Textarea
                    id="translation-editor"
                    value={editedText}
                    onChange={(e) => setEditedText(e.target.value)}
                    rows={4} // Increased rows for more visible space
                    className="text-sm resize-none mt-2"
                    placeholder="Edit the machine translation output here..."
                  />
                </div>

                <div>
                  <Label>Status</Label>
                  <Select value={selectedStatus} onValueChange={setSelectedStatus}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="DRAFT">Draft</SelectItem>
                      <SelectItem value="REVIEWED">Reviewed</SelectItem>
                      <SelectItem value="REQUIRES_REVIEW">Requires Review</SelectItem>
                      <SelectItem value="APPROVED">Approved</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </CardContent>
            </Card>
          </div> {/* End grid layout for side-by-side */}


          {/* 3. MT Outputs in Single Accordion (will now have more vertical space) */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">MT Engine Outputs & Translation Memory</CardTitle>
            </CardHeader>
            <CardContent>
              <Accordion type="multiple" className="w-full">
                <AccordionItem value="mt-outputs">
                  <AccordionTrigger>
                    <span className="font-semibold">MT Engine Outputs ({engineResults.length})</span>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                      {engineResults.map((result, index) => (
                        <ModelOutputCard
                          key={index}
                          result={result}
                          translationStringId={selectedString.id}
                          sourceLanguage={selectedRequest?.sourceLanguage || ''}
                          targetLanguage={selectedRequest?.targetLanguages?.[0] || ''}
                          onCopyToEditor={handleCopyToEditor}
                          onRatingSubmit={onQualityRating}
                          onAnnotationAdd={onAnnotationAdd}
                        />
                      ))}

                      {fuzzyMatches.length > 0 && (
                        <TMMatchesCard
                          fuzzyMatches={fuzzyMatches}
                          onCopyToEditor={handleCopyToEditor}
                        />
                      )}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            </CardContent>
          </Card>

          {/* 4. Translator Details in Separate Collapsible Accordion */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Translator Information</CardTitle>
            </CardHeader>
            <CardContent>
              <Accordion type="single" collapsible className="w-full">
                <AccordionItem value="translator-details">
                  <AccordionTrigger>
                    <span className="font-semibold">Reviewer Details & Assessment</span>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                      <div>
                        <Label htmlFor="reviewer-expertise">Reviewer Expertise</Label>
                        <Select value={reviewerExpertise} onValueChange={setReviewerExpertise}>
                          <SelectTrigger>
                            <SelectValue placeholder="Select expertise level" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="NATIVE">Native Speaker</SelectItem>
                            <SelectItem value="PROFESSIONAL">Professional Translator</SelectItem>
                            <SelectItem value="BILINGUAL">Bilingual</SelectItem>
                            <SelectItem value="LEARNER">Language Learner</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      <div>
                        <Label htmlFor="approval-type">Approval Type</Label>
                        <Select value={approvalType} onValueChange={setApprovalType}>
                          <SelectTrigger>
                            <SelectValue placeholder="How was this approved?" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="IMMEDIATE">Immediate Approval</SelectItem>
                            <SelectItem value="MINOR_EDIT">Minor Edit</SelectItem>
                            <SelectItem value="MAJOR_EDIT">Major Edit</SelectItem>
                            <SelectItem value="COMPLETE_REWRITE">Complete Rewrite</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      <div>
                        <Label htmlFor="cognitive-load">Cognitive Load (1-5)</Label>
                        <Select value={cognitiveLoad.toString()} onValueChange={(value) => setCognitiveLoad(parseInt(value))}>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="1">1 - Very Easy</SelectItem>
                            <SelectItem value="2">2 - Easy</SelectItem>
                            <SelectItem value="3">3 - Moderate</SelectItem>
                            <SelectItem value="4">4 - Difficult</SelectItem>
                            <SelectItem value="5">5 - Very Difficult</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      <div>
                        <Label htmlFor="domain-familiarity">Domain Familiarity (1-5)</Label>
                        <Select value={domainFamiliarity.toString()} onValueChange={(value) => setDomainFamiliarity(parseInt(value))}>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="1">1 - Unfamiliar</SelectItem>
                            <SelectItem value="2">2 - Somewhat Familiar</SelectItem>
                            <SelectItem value="3">3 - Moderately Familiar</SelectItem>
                            <SelectItem value="4">4 - Very Familiar</SelectItem>
                            <SelectItem value="5">5 - Expert</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            </CardContent>
          </Card>
        </div>

        {/* Agent SSE stream panel — shown when refinement is active or complete */}
        {selectedRequest?.advertiserProfileId && refineState[selectedString.id]?.events.length > 0 && (
          <div className="px-6 pb-2">
            <div className="rounded border border-purple-500/30 bg-black/80 p-3 text-xs font-mono space-y-1 max-h-40 overflow-y-auto">
              {refineState[selectedString.id].events.map((ev, i) => {
                if (ev.type === 'narrate') {
                  return <div key={i} className="text-purple-300"><span className="text-purple-500 mr-1">▶</span>{ev.message}</div>;
                }
                if (ev.type === 'iteration') {
                  return (
                    <div key={i} className="border border-purple-700/40 rounded p-2 space-y-1 bg-purple-950/30">
                      <div className="text-purple-200 font-semibold">Attempt {ev.attempt}/2</div>
                      <div className="text-yellow-400">
                        Brand voice: {ev.brand_voice_before?.toFixed(1)} → {ev.brand_voice_after?.toFixed(1)}/5.0
                        {ev.brand_voice_after !== undefined && ev.brand_voice_before !== undefined
                          && ev.brand_voice_after > ev.brand_voice_before
                          ? <span className="text-green-400 ml-1">▲</span>
                          : <span className="text-red-400 ml-1">▼</span>}
                      </div>
                      <div className="text-blue-300 italic truncate">{ev.text}</div>
                    </div>
                  );
                }
                if (ev.type === 'done') {
                  return <div key={i} className="text-green-400 font-semibold">✓ {ev.message} Final score: {ev.final_score?.toFixed(1)}/5.0{ev.was_improved ? ' — translation updated.' : ' — no improvement.'}</div>;
                }
                if (ev.type === 'error') {
                  return <div key={i} className="text-red-400">✗ {ev.message}</div>;
                }
                return null;
              })}
            </div>
          </div>
        )}

        <div className="flex justify-between items-center p-6 border-t bg-muted/30">
          <Button onClick={onPrevious} disabled={currentIndex === 0} variant="outline">
            <ChevronLeft className="w-4 h-4 mr-2" />
            Previous
          </Button>
          <div className="flex gap-2">
            {selectedRequest?.advertiserProfileId && (
              <Button
                variant="outline"
                className="border-purple-500 text-purple-600 hover:bg-purple-50 dark:hover:bg-purple-950"
                onClick={() => onRefine(selectedString.id)}
                disabled={refineState[selectedString.id]?.streaming}
              >
                {refineState[selectedString.id]?.streaming
                  ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Refining…</>
                  : <><Wand2 className="w-4 h-4 mr-2" />Refine with AI</>}
              </Button>
            )}
            <Button onClick={handleUpdate} variant={saveFeedback ? 'default' : 'outline'}>
              {saveFeedback ? <><CheckCircle className="w-4 h-4 mr-2" />Saved!</> : 'Update Translation'}
            </Button>
            <Button onClick={handleApprove} variant={approveFeedback ? 'default' : 'default'} className={approveFeedback ? 'bg-green-600 hover:bg-green-600' : ''}>
              {approveFeedback ? <><CheckCircle className="w-4 h-4 mr-2" />Approved!</> : 'Approve & Next'}
            </Button>
          </div>
          <Button onClick={onNext} disabled={currentIndex === totalCount - 1} variant="outline">
            Next
            <ChevronRight className="w-4 h-4 ml-2" />
          </Button>
        </div>
        </>
        )}
      </div>
    </div>
  );
};

export const TranslationQA: React.FC = () => {
  const [translationRequests, setTranslationRequests] = useState<TranslationRequest[]>([]);
  const [selectedRequest, setSelectedRequest] = useState<TranslationRequest | null>(null);
  const [selectedString, setSelectedString] = useState<TranslationString | null>(null);
  const [editedText, setEditedText] = useState('');
  const [selectedStatus, setSelectedStatus] = useState('');
  const [loading, setLoading] = useState(true);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [bulkReviewMode, setBulkReviewMode] = useState(false);
  const [reviewComplete, setReviewComplete] = useState(false);
  const [segmentConfidence, setSegmentConfidence] = useState<Record<string, { confidence: number | null; n_signals: number; mean_quality: number | null }>>({});
  const [filterLanguage, setFilterLanguage] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [showAnalytics, setShowAnalytics] = useState(false);

  const [submitStatus, setSubmitStatus] = useState<{type: 'success' | 'error' | 'idle', message: string}>({type: 'idle', message: ''});
  const [annotatorId, setAnnotatorId] = useState<string>(
    () => localStorage.getItem('hitl_annotatorId') ?? 'REVIEWER_1'
  );

  const handleAnnotatorChange = (value: string) => {
    setAnnotatorId(value);
    localStorage.setItem('hitl_annotatorId', value);
  };

  const [refineState, setRefineState] = useState<Record<string, RefineState>>({});

  const handleRefine = (stringId: string) => {
    setRefineState(prev => ({
      ...prev,
      [stringId]: { streaming: true, events: [], done: false },
    }));

    const es = new EventSource(`${API_BASE_URL}/api/agent/refine-stream/${stringId}`);

    es.onmessage = (e) => {
      try {
        const event: AgentEvent = JSON.parse(e.data);
        setRefineState(prev => {
          const current = prev[stringId] ?? { streaming: true, events: [], done: false };
          return {
            ...prev,
            [stringId]: {
              ...current,
              events: [...current.events, event],
              streaming: event.type !== 'done' && event.type !== 'error',
              done: event.type === 'done' || event.type === 'error',
              ...(event.type === 'done' ? {
                finalScore: event.final_score,
                wasImproved: event.was_improved,
              } : {}),
            },
          };
        });
        if (event.type === 'done' || event.type === 'error') {
          es.close();
          if (event.type === 'done' && event.was_improved) {
            fetchTranslationRequests();
          }
        }
      } catch { /* ignore parse errors */ }
    };

    es.onerror = () => {
      setRefineState(prev => ({
        ...prev,
        [stringId]: { ...(prev[stringId] ?? { events: [] }), streaming: false, done: true },
      }));
      es.close();
    };
  };

  const [analytics, setAnalytics] = useState({
    totalStrings: 0,
    approvedStrings: 0,
    pendingStrings: 0,
    avgQualityScore: 0,
    totalAnnotations: 0,
    annotationsByCategory: {} as Record<string, number>,
    annotationsBySeverity: {} as Record<string, number>,
  });

  useEffect(() => {
    fetchTranslationRequests();
  }, []);

  useEffect(() => {
    if (selectedRequest) {
      calculateAnalytics();
    }
  }, [selectedRequest]);

  useEffect(() => {
    if (!selectedRequest) return;
    const fetchConfidence = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/analytics/segment-confidence?job_id=${selectedRequest.id}`);
        if (res.ok) {
          const data = await res.json();
          const map: Record<string, { confidence: number | null; n_signals: number; mean_quality: number | null }> = {};
          for (const seg of data.segments ?? []) {
            map[seg.segment_id] = {
              confidence: seg.confidence,
              n_signals: seg.n_signals,
              mean_quality: seg.mean_quality,
            };
          }
          setSegmentConfidence(map);
        }
      } catch { /* silently ignore */ }
    };
    fetchConfidence();
  }, [selectedRequest]);

  const showStatus = (type: 'success' | 'error', message: string) => {
    setSubmitStatus({ type, message });
    setTimeout(() => setSubmitStatus({ type: 'idle', message: '' }), 3000);
  };

  const fetchTranslationRequests = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/translation-requests`);
      if (response.ok) {
        const data = await response.json();
        setTranslationRequests(data);
        if (data.length > 0) {
          setSelectedRequest(data[0]);
        }
      }
    } catch (error) {
      console.error('Failed to fetch translation requests:', error);
      showStatus('error', 'Failed to fetch translation requests');
    } finally {
      setLoading(false);
    }
  };

  const calculateAnalytics = (request = selectedRequest) => {
    if (!request) return;

    const strings = request.translationStrings;
    const totalStrings = strings.length;
    const approvedStrings = strings.filter(s => s.status === 'APPROVED' || s.isApproved).length;
    const pendingStrings = strings.filter(s => s.status === 'REQUIRES_REVIEW').length;

    const allAnnotations = strings.flatMap(s => s.annotations ?? []);
    const totalAnnotations = allAnnotations.length;

    const annotationsByCategory: Record<string, number> = {};
    const annotationsBySeverity: Record<string, number> = {};
    for (const a of allAnnotations) {
      annotationsByCategory[a.category] = (annotationsByCategory[a.category] ?? 0) + 1;
      annotationsBySeverity[a.severity] = (annotationsBySeverity[a.severity] ?? 0) + 1;
    }

    const bleuScores = strings
      .map(s => s.qualityMetrics?.bleuScore)
      .filter(score => score !== undefined && score !== null) as number[];

    const avgQualityScore = bleuScores.length > 0
      ? bleuScores.reduce((sum, score) => sum + score, 0) / bleuScores.length
      : 0;

    setAnalytics({
      totalStrings,
      approvedStrings,
      pendingStrings,
      avgQualityScore,
      totalAnnotations,
      annotationsByCategory,
      annotationsBySeverity,
    });
  };

  const handleStringSelect = (translationString: TranslationString, index: number) => {
    setSelectedString(translationString);
    setEditedText(translationString.translatedText);
    setSelectedStatus(translationString.status);
    setCurrentIndex(index);
  };

  const handleBulkReviewStart = (request: TranslationRequest) => {
    setSelectedRequest(request);
    if (request.translationStrings.length > 0) {
      handleStringSelect(request.translationStrings[0], 0);
      setReviewComplete(false);
      setBulkReviewMode(true);
    }
  };

  const handleUpdateTranslation = async () => {
    if (!selectedString) return;

    try {
      // FIX: Add '/translation-requests' to the path
      const response = await fetch(`${API_BASE_URL}/api/translation-requests/translation-strings/${selectedString.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          translatedText: editedText,
          status: selectedStatus,
          annotatorId,
        })
      });

      if (response.ok) {
        showStatus('success', 'Translation updated successfully!');
        setTranslationRequests(prevRequests =>
          prevRequests.map(request => {
            if (request.id === selectedRequest?.id) {
              return {
                ...request,
                translationStrings: request.translationStrings.map(string => {
                  if (string.id === selectedString.id) {
                    return {
                      ...string,
                      translatedText: editedText,
                      status: selectedStatus
                    };
                  }
                  return string;
                })
              };
            }
            return request;
          })
        );

        setSelectedString(prev => prev ? {
          ...prev,
          translatedText: editedText,
          status: selectedStatus
        } : null);
      } else {
        showStatus('error', 'Failed to update translation');
      }
    } catch (error) {
      console.error('Failed to update translation:', error);
      showStatus('error', 'Failed to update translation');
    }
  };

  const handleApprove = async () => {
    if (!selectedString) return;

    try {
      // FIX: Add '/translation-requests' to the path
      const response = await fetch(`${API_BASE_URL}/api/translation-requests/translation-strings/${selectedString.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          translatedText: editedText,
          status: 'APPROVED',
          annotatorId,
        })
      });

      if (response.ok) {
        showStatus('success', 'Translation approved successfully!');
        setTranslationRequests(prevRequests =>
          prevRequests.map(request => {
            if (request.id === selectedRequest?.id) {
              return {
                ...request,
                translationStrings: request.translationStrings.map(string => {
                  if (string.id === selectedString.id) {
                    return {
                      ...string,
                      translatedText: editedText,
                      status: 'APPROVED',
                      isApproved: true
                    };
                  }
                  return string;
                })
              };
            }
            return request;
          })
        );

        if (selectedString?.id === selectedString.id) {
          setSelectedString(prev => prev ? {
            ...prev,
            translatedText: editedText,
            status: 'APPROVED',
            isApproved: true
          } : null);
          setSelectedStatus('APPROVED');
        }

        const totalStrings = selectedRequest?.translationStrings.length ?? 0;
        if (currentIndex === totalStrings - 1) {
          setReviewComplete(true);
        } else {
          navigateNext();
        }
      } else {
        showStatus('error', 'Failed to approve translation');
      }
    } catch (error) {
      console.error('Failed to approve translation:', error);
      showStatus('error', 'Failed to approve translation');
    }
  };

  const navigatePrevious = () => {
    if (selectedRequest && currentIndex > 0) {
      const newIndex = currentIndex - 1;
      handleStringSelect(selectedRequest.translationStrings[newIndex], newIndex);
    }
  };

  const navigateNext = () => {
    if (selectedRequest && currentIndex < selectedRequest.translationStrings.length - 1) {
      const newIndex = currentIndex + 1;
      handleStringSelect(selectedRequest.translationStrings[newIndex], newIndex);
    }
  };

  const handleQualityRating = async (rating: number, annotations: any[]) => {
    try {
      // FIX: Add '/api/analytics' prefix to quality-rating endpoint
      const response = await fetch(`${API_BASE_URL}/api/analytics/rlhf/quality-rating`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          translationStringId: selectedString?.id,
          qualityScore: rating,
          annotations
        })
      });

      if (response.ok) {
        showStatus('success', 'Quality rating submitted!');
      } else {
        showStatus('error', 'Failed to submit rating');
      }
    } catch (error) {
      showStatus('error', 'Failed to submit rating');
    }
  };

  const handleAnnotationAdd = async (annotation: any) => {
    if (!selectedString) return;

    try {
      // FIX: Add '/translation-requests' to the path for annotations
      const response = await fetch(`${API_BASE_URL}/api/translation-requests/translation-strings/${selectedString.id}/annotations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(annotation)
      });

      if (response.ok) {
        showStatus('success', 'Annotation added successfully!');
      } else {
        showStatus('error', 'Failed to add annotation');
      }
    } catch (error) {
      console.error('Failed to add annotation:', error);
      showStatus('error', 'Failed to add annotation');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'approved':
        return 'bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400';
      case 'reviewed':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400';
      case 'requires_review': // Changed from 'requires review'
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400';
      case 'multi_engine_review':
        return 'bg-purple-100 text-purple-800 dark:bg-purple-900/20 dark:text-purple-400';
      case 'draft':
        return 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300';
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300';
    }
  };

  const getFilteredStrings = () => {
    if (!selectedRequest) return [];

    return selectedRequest.translationStrings.filter(string => {
      const matchesLanguage = filterLanguage === 'all' || string.targetLanguage.toLowerCase() === filterLanguage.toLowerCase();
      const matchesStatus = filterStatus === 'all' || string.status.toLowerCase() === filterStatus.toLowerCase();
      const matchesSearch = searchTerm === '' ||
        string.sourceText.toLowerCase().includes(searchTerm.toLowerCase()) ||
        string.translatedText.toLowerCase().includes(searchTerm.toLowerCase());

      return matchesLanguage && matchesStatus && matchesSearch;
    });
  };

  const getProgressPercentage = (request: TranslationRequest) => {
    const total = request.translationStrings.length;
    const approved = request.translationStrings.filter(s =>
      s.status === 'APPROVED' || s.isApproved
    ).length;
    return total > 0 ? (approved / total) * 100 : 0;
  };

  const getConfidenceBadge = (stringId: string) => {
    const conf = segmentConfidence[stringId];
    if (!conf) return null;
    const { confidence, n_signals } = conf;
    if (confidence === null || n_signals < 2) {
      return <Badge variant="outline" className="text-xs text-muted-foreground">Conf: —</Badge>;
    }
    const pct = Math.round(confidence * 100);
    if (confidence >= 0.7) {
      return <Badge variant="outline" className="text-xs border-green-500 text-green-600 dark:text-green-400">Conf: {pct}%</Badge>;
    } else if (confidence >= 0.4) {
      return <Badge variant="outline" className="text-xs border-yellow-500 text-yellow-600 dark:text-yellow-400">Conf: {pct}%</Badge>;
    } else {
      return <Badge variant="outline" className="text-xs border-red-500 text-red-600 dark:text-red-400">Conf: {pct}%</Badge>;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-primary mx-auto"></div>
          <p className="mt-4 text-muted-foreground">Loading translation requests...</p>
        </div>
      </div>
    );
  }

  const filteredStrings = getFilteredStrings();

  return (
    <div className="min-h-screen bg-background">
      <div className="bg-card border-b px-6 py-4">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-bold">MT Post-Editing</h1>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <Label htmlFor="annotator-id" className="text-sm text-muted-foreground whitespace-nowrap">Reviewing as</Label>
              <Select value={annotatorId} onValueChange={handleAnnotatorChange}>
                <SelectTrigger id="annotator-id" className="w-36 h-8 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="REVIEWER_1">Reviewer 1</SelectItem>
                  <SelectItem value="REVIEWER_2">Reviewer 2</SelectItem>
                  <SelectItem value="REVIEWER_3">Reviewer 3</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button
              onClick={async () => {
                if (!showAnalytics && selectedRequest) {
                  // Re-fetch the job to get fresh annotations before showing
                  try {
                    const res = await fetch(`${API_BASE_URL}/api/translation-requests/${selectedRequest.id}`);
                    if (res.ok) {
                      const fresh = await res.json();
                      setSelectedRequest(fresh);
                      calculateAnalytics(fresh);
                    }
                  } catch { /* fall back to cached data */ }
                }
                setShowAnalytics(!showAnalytics);
              }}
              variant="outline"
              size="sm"
            >
              <BarChart3 className="w-4 h-4 mr-2" />
              Analytics
            </Button>
            <Button onClick={fetchTranslationRequests} variant="outline" size="sm">
              Refresh
            </Button>
          </div>
        </div>
      </div>

      {submitStatus.type !== 'idle' && (
        <div className={`px-6 py-3 border-b ${
          submitStatus.type === 'success'
            ? 'bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800'
            : 'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800'
        }`}>
          <div className="flex items-center">
            {submitStatus.type === 'success' ?
              <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400 mr-2" /> :
              <XCircle className="w-5 h-5 text-red-600 dark:text-red-400 mr-2" />
            }
            <span className={
              submitStatus.type === 'success'
                ? 'text-green-800 dark:text-green-200'
                : 'text-red-800 dark:text-red-200'
            }>
              {submitStatus.message}
            </span>
          </div>
        </div>
      )}

      {showAnalytics && (
        <div className="bg-card border-b px-6 py-4 space-y-3">
          <div className="grid grid-cols-4 gap-4">
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold">{analytics.totalStrings}</div>
                <div className="text-sm text-muted-foreground">Total Strings</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-green-600 dark:text-green-400">{analytics.approvedStrings}</div>
                <div className="text-sm text-muted-foreground">Approved</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">{analytics.pendingStrings}</div>
                <div className="text-sm text-muted-foreground">Pending</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">{(analytics.avgQualityScore * 100).toFixed(1)}%</div>
                <div className="text-sm text-muted-foreground">Avg BLEU</div>
              </CardContent>
            </Card>
          </div>
          {analytics.totalAnnotations > 0 && (
            <div className="grid grid-cols-2 gap-4">
              <Card>
                <CardContent className="p-4">
                  <div className="text-sm font-medium mb-2">Annotations by category <span className="text-muted-foreground font-normal">({analytics.totalAnnotations} total)</span></div>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(analytics.annotationsByCategory).sort((a, b) => b[1] - a[1]).map(([cat, count]) => (
                      <span key={cat} className="text-xs bg-muted px-2 py-1 rounded capitalize">{cat}: {count}</span>
                    ))}
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4">
                  <div className="text-sm font-medium mb-2">Annotations by severity</div>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(analytics.annotationsBySeverity).sort((a, b) => b[1] - a[1]).map(([sev, count]) => (
                      <span key={sev} className={`text-xs px-2 py-1 rounded capitalize ${
                        sev === 'CRITICAL' ? 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300' :
                        sev === 'HIGH' ? 'bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300' :
                        sev === 'MEDIUM' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300' :
                        'bg-muted'
                      }`}>{sev}: {count}</span>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
          {analytics.totalAnnotations === 0 && (
            <p className="text-sm text-muted-foreground">No annotations on this job.</p>
          )}
        </div>
      )}

      <div className="flex h-[calc(100vh-120px)]">
        <div className="w-1/3 bg-card border-r overflow-y-auto">
          <div className="p-4 border-b">
            <h2 className="font-semibold">Translation Requests</h2>
          </div>
          <div className="p-4 space-y-3">
            {translationRequests.map((request) => {
              const progressPercent = getProgressPercentage(request);
              const approvedCount = request.translationStrings.filter(s =>
                s.status === 'APPROVED' || s.isApproved
              ).length;
              const totalCount = request.translationStrings.length;

              return (
                <Card
                  key={request.id}
                  className={`cursor-pointer transition-colors ${
                    selectedRequest?.id === request.id
                      ? 'ring-2 ring-primary'
                      : 'hover:bg-muted/50'
                  }`}
                  onClick={() => setSelectedRequest(request)}
                >
                  <CardContent className="p-4">
                    <div className="space-y-2">
                      <div className="font-medium text-sm">{request.fileName}</div>
                      <div className="text-xs text-muted-foreground">
                        {request.sourceLanguage} → {request.targetLanguages.join(', ')}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {request.wordCount.toLocaleString()} words
                      </div>
                      {request.requestType === 'MULTI_ENGINE' && (
                        <Badge variant="secondary" className="text-xs">
                          Multi-Model
                        </Badge>
                      )}
                      <div className="space-y-1">
                        <div className="flex justify-between text-xs">
                          <span>Progress</span>
                          <span>{approvedCount} of {totalCount}</span>
                        </div>
                        <Progress value={progressPercent} className="h-2" />
                      </div>
                      <Button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleBulkReviewStart(request);
                        }}
                        size="sm"
                        className="w-full"
                      >
                        Start Bulk Review
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>

        <div className="w-2/3 flex flex-col">
          <div className="p-4 border-b bg-card">
            <div className="flex justify-between items-center mb-4">
              <h2 className="font-semibold">Translation Strings</h2>
              {selectedRequest && (
                <span className="text-sm text-muted-foreground">
                  {filteredStrings.length} of {selectedRequest.translationStrings.length}
                </span>
              )}
            </div>

            <div className="flex gap-2">
              <Input
                placeholder="Search translations..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="flex-1"
              />
              <Select value={filterLanguage} onValueChange={setFilterLanguage}>
                <SelectTrigger className="w-40">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Languages</SelectItem>
                  <SelectItem value="en">English</SelectItem>
                  <SelectItem value="fr">French</SelectItem>
                  <SelectItem value="jp">Japanese</SelectItem>
                </SelectContent>
              </Select>
              <Select value={filterStatus} onValueChange={setFilterStatus}>
                <SelectTrigger className="w-40">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="approved">Approved</SelectItem>
                  <SelectItem value="reviewed">Reviewed</SelectItem>
                  <SelectItem value="requires_review">Requires Review</SelectItem>
                  <SelectItem value="multi_engine_review">Multi-Model Review</SelectItem>
                  <SelectItem value="draft">Draft</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto">
            {selectedRequest ? (
              <div className="p-4 space-y-3">
                {filteredStrings.map((string, index) => (
                  <Card
                    key={string.id}
                    className="cursor-pointer hover:bg-muted/50 transition-colors"
                    onClick={() => handleStringSelect(string, index)}
                  >
                    <CardContent className="p-4">
                      <div className="space-y-2">
                        <div className="text-sm font-medium">{string.sourceText}</div>
                        <div className="text-sm text-muted-foreground">{string.translatedText}</div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <Badge className={getStatusColor(string.status)}>
                            {string.status}
                          </Badge>
                          {string.qualityMetrics?.bleuScore && (
                            <Badge variant="outline" className="text-xs">
                              BLEU: {(string.qualityMetrics.bleuScore * 100).toFixed(1)}%
                            </Badge>
                          )}
                          {string.annotations.length > 0 && (
                            <Badge variant="outline" className="text-xs">
                              <MessageSquare className="w-3 h-3 mr-1" />
                              {string.annotations.length}
                            </Badge>
                          )}
                          {string.rlhfSubmitted && (
                            <Badge variant="outline" className="text-xs">
                              RLHF
                            </Badge>
                          )}
                          {string.fuzzyMatches && string.fuzzyMatches.length > 0 && (
                            <Badge variant="outline" className="text-xs">
                              🔍 TM
                            </Badge>
                          )}
                          {string.engineResults && string.engineResults.length > 0 && (
                            <Badge variant="outline" className="text-xs">
                              🤖 Multi
                            </Badge>
                          )}
                          {getConfidenceBadge(string.id)}
                          {refineState[string.id]?.done && refineState[string.id]?.wasImproved && (
                            <Badge className="text-xs bg-purple-600 text-white hover:bg-purple-600">
                              ✨ REFINED
                            </Badge>
                          )}
                          {selectedRequest?.advertiserProfileId && (
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-6 px-2 text-xs ml-auto border-purple-500 text-purple-600 hover:bg-purple-50 dark:hover:bg-purple-950"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleRefine(string.id);
                              }}
                              disabled={refineState[string.id]?.streaming}
                            >
                              {refineState[string.id]?.streaming
                                ? <><Loader2 className="w-3 h-3 mr-1 animate-spin" />Refining…</>
                                : <><Wand2 className="w-3 h-3 mr-1" />Refine</>
                              }
                            </Button>
                          )}
                        </div>

                        {/* SSE stream panel */}
                        {refineState[string.id]?.events.length > 0 && (
                          <div
                            className="mt-2 rounded border border-purple-500/30 bg-black/80 p-3 text-xs font-mono space-y-1 max-h-48 overflow-y-auto"
                            onClick={(e) => e.stopPropagation()}
                          >
                            {refineState[string.id].events.map((ev, i) => {
                              if (ev.type === 'narrate') {
                                return (
                                  <div key={i} className="text-purple-300">
                                    <span className="text-purple-500 mr-1">▶</span>{ev.message}
                                  </div>
                                );
                              }
                              if (ev.type === 'iteration') {
                                return (
                                  <div key={i} className="border border-purple-700/40 rounded p-2 space-y-1 bg-purple-950/30">
                                    <div className="text-purple-200 font-semibold">Attempt {ev.attempt}/2</div>
                                    <div className="text-yellow-400">
                                      Brand voice: {ev.brand_voice_before?.toFixed(1)} → {ev.brand_voice_after?.toFixed(1)}/5.0
                                      {ev.brand_voice_after !== undefined && ev.brand_voice_before !== undefined && ev.brand_voice_after > ev.brand_voice_before
                                        ? <span className="text-green-400 ml-1">▲</span>
                                        : <span className="text-red-400 ml-1">▼</span>
                                      }
                                    </div>
                                    <div className="text-blue-300 italic truncate">{ev.text}</div>
                                  </div>
                                );
                              }
                              if (ev.type === 'done') {
                                return (
                                  <div key={i} className="text-green-400 font-semibold">
                                    ✓ {ev.message} Final score: {ev.final_score?.toFixed(1)}/5.0
                                    {ev.was_improved ? ' — translation updated.' : ' — no improvement.'}
                                  </div>
                                );
                              }
                              if (ev.type === 'error') {
                                return (
                                  <div key={i} className="text-red-400">
                                    ✗ {ev.message}
                                  </div>
                                );
                              }
                              return null;
                            })}
                          </div>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-muted-foreground">
                Select a translation request to view strings
              </div>
            )}
          </div>
        </div>
      </div>

      {bulkReviewMode && selectedString && (() => {
        const strings = selectedRequest?.translationStrings ?? [];
        const totalCount = strings.length;
        const approvedCount = strings.filter(s => s.status === 'APPROVED' || s.isApproved).length;
        return (
          <BulkReviewOverlay
            selectedString={selectedString}
            editedText={editedText}
            setEditedText={setEditedText}
            selectedStatus={selectedStatus}
            setSelectedStatus={setSelectedStatus}
            onClose={() => { setBulkReviewMode(false); setReviewComplete(false); }}
            onContinueReviewing={() => { setReviewComplete(false); navigatePrevious(); }}
            onUpdate={handleUpdateTranslation}
            onApprove={handleApprove}
            onNext={navigateNext}
            onPrevious={navigatePrevious}
            currentIndex={currentIndex}
            totalCount={totalCount}
            approvedCount={approvedCount}
            reviewComplete={reviewComplete}
            onQualityRating={handleQualityRating}
            onAnnotationAdd={handleAnnotationAdd}
            selectedRequest={selectedRequest}
            stringConfidence={selectedString ? segmentConfidence[selectedString.id] : undefined}
            onRefine={handleRefine}
            refineState={refineState}
          />
        );
      })()}
    </div>
  );
};

export default TranslationQA;