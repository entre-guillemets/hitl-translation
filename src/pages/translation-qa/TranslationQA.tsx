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
import { BarChart3, CheckCircle, ChevronLeft, ChevronRight, Copy, MessageSquare, X, XCircle } from 'lucide-react';
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
  metricXScore?: number;
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
  qualityMetrics: any[];
  requestDate: string;
  wordCount: number;
  requestType?: string;
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
    'mt5_multilingual': 'mT5 Multilingual',
    'opus_enhanced': 'OPUS Enhanced',
    't5_versatile': 'mT5 Versatile', // Added for consistency
    'nllb_multilingual': 'NLLB Multilingual', // Added for consistency
  };
  return names[engine] || engine;
};

const getEngineIcon = (engine: string) => {
  const icons: { [key: string]: string } = {
    'opus_fast': '⚡',
    'elan_specialist': '🎯',
    'mt5_multilingual': '🌐',
    'opus_enhanced': '⭐',
    't5_versatile': '🤖', // Added for consistency
    'nllb_multilingual': '🌍', // Added for consistency
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
        
        // Call select-engine endpoint to set this as the base translation
        await fetch(`${API_BASE_URL}/api/translation-strings/${translationStringId}/select-engine`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                engine: result.engine,
                rating: 3, // Default rating
                comments: "Selected via copy button"
            })
        });
        
        // Track preference
        await fetch(`${API_BASE_URL}/api/translation-preferences`, {
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
    
    await fetch(`${API_BASE_URL}/api/rlhf/quality-rating`, { // Changed to rlhf/quality-rating as per your initial main.py
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        translationStringId,
        qualityScore: rating, // Changed to qualityScore
        annotations: annotationList // Pass annotation list
      })
    });
    
    onRatingSubmit(rating, annotationList);
    setAnnotations('');
  };

  const handleAnnotationSubmit = async () => { // Made async
    if (newAnnotation.category && newAnnotation.comment && translationStringId) { // Check translationStringId
      try {
        await fetch(`${API_BASE_URL}/api/translation-strings/${translationStringId}/annotations`, { // Call specific endpoint
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
          Confidence: {(result.confidence * 100).toFixed(0)}%
        </div>

        <Button 
          onClick={handleCopy} 
          size="sm" 
          className="w-full"
          variant={showCopySuccess ? "default" : "outline"}
        >
          <Copy className="w-4 h-4 mr-2" />
          {showCopySuccess ? "Copied!" : "Copy"}
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
        {fuzzyMatches.map((match: any, index: number) => (
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
  onUpdate: () => void;
  onApprove: () => void;
  onNext: () => void;
  onPrevious: () => void;
  currentIndex: number;
  totalCount: number;
  onQualityRating: (rating: number, annotations: any[]) => void;
  onAnnotationAdd: (annotation: any) => void;
  selectedRequest: TranslationRequest | null;
}> = ({
  selectedString,
  editedText,
  setEditedText,
  selectedStatus,
  setSelectedStatus,
  onClose,
  onUpdate,
  onApprove,
  onNext,
  onPrevious,
  currentIndex,
  totalCount,
  onQualityRating,
  onAnnotationAdd,
  selectedRequest
}) => {
  const engineResults = selectedString.engineResults || [];
  const fuzzyMatches = selectedString.fuzzyMatches || [];
  
  // Translator details state
  const [reviewerExpertise, setReviewerExpertise] = useState('');
  const [approvalType, setApprovalType] = useState('');
  const [cognitiveLoad, setCognitiveLoad] = useState(3);
  const [domainFamiliarity, setDomainFamiliarity] = useState(3);

  const handleCopyToEditor = (text: string) => {
    setEditedText(text);
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-background rounded-lg shadow-xl w-full max-w-7xl h-[90vh] flex flex-col border">
        <div className="flex justify-between items-center p-6 border-b bg-muted/30">
          <h2 className="text-xl font-semibold">Bulk Review Mode</h2>
          <div className="flex items-center gap-4">
            <span className="text-sm text-muted-foreground">
              {currentIndex + 1} / {totalCount}
            </span>
            <Button onClick={onClose} variant="outline" size="sm">
              <X className="w-4 h-4" />
            </Button>
          </div>
        </div>

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

                {selectedString.qualityMetrics && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Quality Assessment</CardTitle>
                    </CardHeader>
                    <CardContent className="flex gap-4 text-xs">
                      <div>MetricX: {selectedString.qualityMetrics.metricXScore?.toFixed(1) || 'N/A'}</div>
                      {selectedString.qualityMetrics.bleuScore && (
                        <div>BLEU: {(selectedString.qualityMetrics.bleuScore * 100).toFixed(1)}%</div>
                      )}
                      {selectedString.qualityMetrics.cometScore && (
                        <div>COMET: {(selectedString.qualityMetrics.cometScore * 100).toFixed(1)}%</div>
                      )}
                      {selectedString.qualityMetrics.terScore && (
                        <div>TER: {(selectedString.qualityMetrics.terScore).toFixed(1)}%</div> //* TER is already % from backend */}
                      )}
                    </CardContent>
                  </Card>
                )}
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

        <div className="flex justify-between items-center p-6 border-t bg-muted/30">
          <Button onClick={onPrevious} disabled={currentIndex === 0} variant="outline">
            <ChevronLeft className="w-4 h-4 mr-2" />
            Previous
          </Button>
          <div className="flex gap-2">
            <Button onClick={onUpdate} variant="outline">
              Update Translation
            </Button>
            <Button onClick={onApprove}>
              Approve & Next
            </Button>
          </div>
          <Button onClick={onNext} disabled={currentIndex === totalCount - 1} variant="outline">
            Next
            <ChevronRight className="w-4 h-4 ml-2" />
          </Button>
        </div>
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
  const [filterLanguage, setFilterLanguage] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [showAnalytics, setShowAnalytics] = useState(false);

  const [submitStatus, setSubmitStatus] = useState<{type: 'success' | 'error' | 'idle', message: string}>({type: 'idle', message: ''});

  const [analytics, setAnalytics] = useState({
    totalStrings: 0,
    approvedStrings: 0,
    pendingStrings: 0,
    avgQualityScore: 0,
    totalAnnotations: 0
  });

  useEffect(() => {
    fetchTranslationRequests();
  }, []);

  useEffect(() => {
    if (selectedRequest) {
      calculateAnalytics();
    }
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

  const calculateAnalytics = () => {
    if (!selectedRequest) return;

    const strings = selectedRequest.translationStrings;
    const totalStrings = strings.length;
    const approvedStrings = strings.filter(s => s.status === 'APPROVED' || s.isApproved).length;
    const pendingStrings = strings.filter(s => s.status === 'REQUIRES_REVIEW').length;
    const totalAnnotations = strings.reduce((sum, s) => sum + s.annotations.length, 0);

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
      totalAnnotations
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
      setBulkReviewMode(true);
    }
  };

  const handleUpdateTranslation = async () => {
    if (!selectedString) return;

    try {
      const response = await fetch(`${API_BASE_URL}/api/translation-strings/${selectedString.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          translatedText: editedText,
          status: selectedStatus
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
      const response = await fetch(`${API_BASE_URL}/api/translation-strings/${selectedString.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          translatedText: editedText,
          status: 'APPROVED'
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

        navigateNext();
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
      const response = await fetch(`${API_BASE_URL}/api/rlhf/quality-rating`, {
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
      const response = await fetch(`${API_BASE_URL}/api/translation-strings/${selectedString.id}/annotations`, {
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
      const matchesLanguage = filterLanguage === 'all' || string.targetLanguage.toLowerCase() === filterLanguage.toLowerCase(); // Added .toLowerCase()
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
      s.status === 'APPROVED' || s.isApproved // 'Approved' string literal removed for consistency
    ).length;
    return total > 0 ? (approved / total) * 100 : 0;
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
          <div className="flex gap-2">
            <Button
              onClick={() => setShowAnalytics(!showAnalytics)}
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
        <div className="bg-card border-b px-6 py-4">
          <div className="grid grid-cols-5 gap-4">
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
                <div className="text-sm text-muted-foreground">Avg Quality</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">{analytics.totalAnnotations}</div>
                <div className="text-sm text-muted-foreground">Annotations</div>
              </CardContent>
            </Card>
          </div>
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
                        </div>
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

      {bulkReviewMode && selectedString && (
        <BulkReviewOverlay
          selectedString={selectedString}
          editedText={editedText}
          setEditedText={setEditedText}
          selectedStatus={selectedStatus}
          setSelectedStatus={setSelectedStatus}
          onClose={() => setBulkReviewMode(false)}
          onUpdate={handleUpdateTranslation}
          onApprove={handleApprove}
          onNext={navigateNext}
          onPrevious={navigatePrevious}
          currentIndex={currentIndex}
          totalCount={selectedRequest?.translationStrings.length || 0}
          onQualityRating={handleQualityRating}
          onAnnotationAdd={handleAnnotationAdd}
          selectedRequest={selectedRequest}
        />
      )}
    </div>
  );
};

export default TranslationQA;