"use client"

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { MultiSelect } from '@/components/ui/multi-select';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { ArrowLeft, Merge, Pause, Play, Save, Split } from 'lucide-react';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { API_BASE_URL } from '@/config/api';

const languageOptions = [
  { label: 'English', value: 'EN' },
  { label: 'Japanese', value: 'JA' },
  { label: 'French', value: 'FR' },
  { label: 'Swahili', value: 'SW' },
];


const LANGUAGE_PAIR_MODELS = {
  'EN-JA': [
    { id: 'opus_fast', label: 'OPUS Fast', description: 'Fast Helsinki-NLP models' },
    { id: 'nllb_multilingual', label: 'NLLB Multilingual', description: 'NLLB model for various languages' },
    { id: 'gemini_transcreation', label: 'Gemini Transcreation', description: 'Cultural adaptation via Gemini' },
  ],
  'JA-EN': [
    { id: 'opus_fast', label: 'OPUS Fast', description: 'Fast Helsinki-NLP models' },
    { id: 'elan_quality', label: 'ELAN Quality', description: 'Japanese specialist model' },
    { id: 'nllb_multilingual', label: 'NLLB Multilingual', description: 'NLLB model for various languages' },
    { id: 'gemini_transcreation', label: 'Gemini Transcreation', description: 'Cultural adaptation via Gemini' },
  ],
  'EN-FR': [
    { id: 'opus_fast', label: 'OPUS Fast', description: 'Fast Helsinki-NLP models' },
    { id: 'elan_quality', label: 'ELAN Quality', description: 'Quality-focused model' },
    { id: 'nllb_multilingual', label: 'NLLB Multilingual', description: 'NLLB model for various languages' },
    { id: 'gemini_transcreation', label: 'Gemini Transcreation', description: 'Cultural adaptation via Gemini' },
  ],
  'FR-EN': [
    { id: 'opus_fast', label: 'OPUS Fast', description: 'Fast Helsinki-NLP models' },
    { id: 'elan_quality', label: 'ELAN Quality', description: 'Quality-focused model' },
    { id: 'nllb_multilingual', label: 'NLLB Multilingual', description: 'NLLB model for various languages' },
    { id: 'gemini_transcreation', label: 'Gemini Transcreation', description: 'Cultural adaptation via Gemini' },
  ],
  'JA-FR': [
    { id: 'opus_fast', label: 'OPUS Fast', description: 'JA→EN→FR pivot via OPUS' },
    { id: 'elan_quality', label: 'ELAN Quality', description: 'JA→EN→FR pivot via ELAN' },
    { id: 'nllb_multilingual', label: 'NLLB Multilingual', description: 'NLLB model for various languages' },
    { id: 'gemini_transcreation', label: 'Gemini Transcreation', description: 'Cultural adaptation via Gemini' },
  ],
  'FR-JA': [
    { id: 'opus_fast', label: 'OPUS Fast', description: 'FR→EN→JA pivot via OPUS' },
    { id: 'elan_quality', label: 'ELAN Quality', description: 'FR→EN→JA pivot via ELAN' },
    { id: 'nllb_multilingual', label: 'NLLB Multilingual', description: 'NLLB model for various languages' },
    { id: 'gemini_transcreation', label: 'Gemini Transcreation', description: 'Cultural adaptation via Gemini' },
  ],
  // Swahili: NLLB-200 only. No dedicated Helsinki model. LLM judge is the
  // primary quality signal — automatic metrics (BLEU/TER) are low-reliability for SW.
  'EN-SW': [
    { id: 'nllb_multilingual', label: 'NLLB Multilingual', description: 'NLLB-200 (swh_Latn) — only available model for EN→SW' },
    { id: 'gemini_transcreation', label: 'Gemini Transcreation', description: 'LLM-based — recommended primary signal for SW' },
  ],
  'SW-EN': [
    { id: 'nllb_multilingual', label: 'NLLB Multilingual', description: 'NLLB-200 (swh_Latn→eng_Latn) — only available model for SW→EN' },
    { id: 'gemini_transcreation', label: 'Gemini Transcreation', description: 'LLM-based — recommended primary signal for SW' },
  ],
};

const requiresSegmentation = (fileType: string): boolean => {
  return fileType.startsWith('image/') || fileType.startsWith('audio/');
};

// ===== SEGMENTATION EDITOR COMPONENT =====
interface SegmentData {
  id: number;
  text: string;
  confidence?: number;
  bbox?: { x: number; y: number; w: number; h: number };
  timestamp?: { start: number; end: number };
}

interface SegmentationEditorProps {
  segmentationData: any;
  onSave: (payload: any) => void;
  onCancel: () => void;
  // State setters passed down to allow interaction
  sourceLanguage: string;
  setSourceLanguage: React.Dispatch<React.SetStateAction<string>>;
  targetLanguages: string[];
  setTargetLanguages: React.Dispatch<React.SetStateAction<string[]>>;
  useMultiEngine: boolean;
  setUseMultiEngine: React.Dispatch<React.SetStateAction<boolean>>;
  selectedEngines: string[];
  setSelectedEngines: React.Dispatch<React.SetStateAction<string[]>>;
}

const SegmentationEditor: React.FC<SegmentationEditorProps> = ({
  segmentationData,
  onSave,
  onCancel,
  sourceLanguage,
  setSourceLanguage,
  targetLanguages,
  setTargetLanguages,
  useMultiEngine,
  setUseMultiEngine,
  selectedEngines,
  setSelectedEngines,
}) => {
  const [segments, setSegments] = useState<SegmentData[]>(segmentationData?.segments || []);
  const [selectedSegments, setSelectedSegments] = useState<Set<number>>(new Set());
  const [mediaType, setMediaType] = useState(segmentationData?.mediaType || 'image');
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [highlightedSegment, setHighlightedSegment] = useState<SegmentData | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [naturalImageSize, setNaturalImageSize] = useState<{ w: number; h: number } | null>(null);
  const imageContainerRef = useRef<HTMLDivElement>(null);

  const audioRef = useRef<HTMLAudioElement>(null);

  const availableModels = useMemo(() => {
    if (!sourceLanguage || targetLanguages.length === 0) return [];
    
    const allModels: Array<{id: string, label: string, icon?: string, description: string, pairs: string[]}> = [];
    
    targetLanguages.forEach(target => {
      const pair = `${sourceLanguage}-${target}`;
      const pairModels = LANGUAGE_PAIR_MODELS[pair as keyof typeof LANGUAGE_PAIR_MODELS] || [];
      
      pairModels.forEach(model => {
        const existingModel = allModels.find(m => m.id === model.id);
        if (existingModel) {
          existingModel.pairs.push(pair);
        } else {
          allModels.push({
            ...model,
            pairs: [pair]
          });
        }
      });
    });
    
    return allModels;
  }, [sourceLanguage, targetLanguages]);

  useEffect(() => {
    if (mediaType === 'audio' && segmentationData?.mediaData) {
      if (audioRef.current) {
        audioRef.current.src = `data:audio/mp3;base64,${segmentationData.mediaData}`;
      }
    }
  }, [mediaType, segmentationData]);

  useEffect(() => {
    if (availableModels.length > 0 && selectedEngines.length === 0) {
      const defaultSelection = availableModels.map(m => m.id);
      setSelectedEngines(defaultSelection);
    }
  }, [availableModels, selectedEngines.length, setSelectedEngines]);

  const togglePlayback = () => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
      } else {
        audioRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const seekTo = (timestamp: { start: number; end: number }) => {
    if (audioRef.current) {
      audioRef.current.currentTime = timestamp.start;
      
      if (isPlaying) {
        audioRef.current.pause();
        setIsPlaying(false);
      }
    }
    setCurrentTime(timestamp.start);
    setHighlightedSegment(segments.find(s => s.timestamp?.start === timestamp.start) || null);
  };
  
  const duration = audioRef.current?.duration || 10.0;
  
  useEffect(() => {
    if (mediaType === 'audio' && isPlaying) {
      const activeSegment = segments.find(s => 
        s.timestamp && currentTime >= s.timestamp.start && currentTime < s.timestamp.end
      );
      setHighlightedSegment(activeSegment || null);
    }
    
    if (audioRef.current && isPlaying && currentTime >= audioRef.current.duration) {
      audioRef.current.pause();
      setIsPlaying(false);
    }
    
  }, [currentTime, isPlaying, segments, mediaType]);

  const handleSegmentClick = (segmentId: number) => {
    const newSelection = new Set(selectedSegments);
    if (newSelection.has(segmentId)) {
      newSelection.delete(segmentId);
    } else {
      newSelection.add(segmentId);
    }
    setSelectedSegments(newSelection);
  };

  const splitSegment = (segmentId: number, splitPosition: number) => {
    const segment = segments.find(s => s.id === segmentId);
    if (!segment) return;

    const text = segment.text;
    const beforeText = text.substring(0, splitPosition).trim();
    const afterText = text.substring(splitPosition).trim();

    if (!beforeText || !afterText) return;

    let nextSegmentId = Math.max(...segments.map(s => s.id)) + 1;
    
    const newSegments: SegmentData[] = [];
    let segmentIndex = -1;

    segments.forEach((s, index) => {
      if (s.id === segmentId) {
        segmentIndex = index;
        newSegments.push({ ...s, text: beforeText });
      } else {
        newSegments.push(s);
      }
    });

    if (segmentIndex === -1) return;

    const splitTime = segment.timestamp ? 
      segment.timestamp.start + (segment.timestamp.end - segment.timestamp.start) * (splitPosition / text.length) : 
      undefined;

    const newSegment: SegmentData = {
      id: nextSegmentId,
      text: afterText,
      timestamp: segment.timestamp && splitTime !== undefined ? {
        start: splitTime,
        end: segment.timestamp.end
      } : undefined,
      bbox: segment.bbox ? { ...segment.bbox, y: segment.bbox.y + segment.bbox.h + 5 } : undefined
    };

    newSegments.splice(segmentIndex + 1, 0, newSegment);
    // Renumber sequentially so bounding box labels stay in sync with the right panel
    setSegments(newSegments.map((s, i) => ({ ...s, id: i + 1 })));
    setSelectedSegments(new Set());
  };

  const mergeSelectedSegments = () => {
    if (selectedSegments.size < 2) return;

    const selectedIds = Array.from(selectedSegments);
    const selectedSegmentObjects = segments.filter(s => selectedIds.includes(s.id));
    selectedSegmentObjects.sort((a, b) => a.id - b.id); // Sort by original ID for merging order

    const mergedText = selectedSegmentObjects.map(s => s.text).join(' ');
    const firstSegment = selectedSegmentObjects[0];
    const lastSegment = selectedSegmentObjects[selectedSegmentObjects.length - 1];

    // Compute union bounding box across all merged segments that have one
    const bboxes = selectedSegmentObjects.map(s => s.bbox).filter(Boolean) as NonNullable<SegmentData['bbox']>[];
    const unionBbox = bboxes.length > 0 ? {
      x: Math.min(...bboxes.map(b => b.x)),
      y: Math.min(...bboxes.map(b => b.y)),
      w: Math.max(...bboxes.map(b => b.x + b.w)) - Math.min(...bboxes.map(b => b.x)),
      h: Math.max(...bboxes.map(b => b.y + b.h)) - Math.min(...bboxes.map(b => b.y)),
    } : undefined;

    const mergedSegment: SegmentData = {
      ...firstSegment,
      text: mergedText,
      bbox: unionBbox,
      timestamp: firstSegment.timestamp && lastSegment.timestamp ? {
        start: firstSegment.timestamp.start,
        end: lastSegment.timestamp.end
      } : undefined
    };

    const newSegments = segments.filter(s => !selectedIds.includes(s.id));

    const insertionIndex = segments.findIndex(s => s.id === firstSegment.id);
    if (insertionIndex !== -1) {
        newSegments.splice(insertionIndex, 0, mergedSegment);
    } else {
        newSegments.push(mergedSegment);
    }

    newSegments.sort((a, b) => a.id - b.id);
    // Renumber sequentially so bounding box labels stay in sync with the right panel
    const renumbered = newSegments.map((s, i) => ({ ...s, id: i + 1 }));

    setSegments(renumbered);
    setSelectedSegments(new Set());
  };

  const handleSave = async () => {
    // Basic validation check
    if (targetLanguages.length === 0) {
      alert("Please select at least one Target Language before saving.");
      return;
    }
    if (useMultiEngine && selectedEngines.length === 0) {
      alert("In Multi-Model mode, please select at least one engine.");
      return;
    }

    setIsSaving(true);
    try {
      const segmentationPayload = {
        segments,
        sourceLanguage,
        targetLanguages,
        fileName: segmentationData.fileName,
        requestType: useMultiEngine ? "multi" : "single",
        engines: useMultiEngine ? selectedEngines : undefined
      };
      
      await onSave(segmentationPayload);
    } catch (error) {
      console.error("Failed to save segmentation:", error);
    } finally {
      setIsSaving(false);
    }
  };

  const EditableSegment = ({ segment }: { segment: SegmentData }) => {
    const [isEditing, setIsEditing] = useState(false);
    const [editText, setEditText] = useState(segment.text);

    const saveEdit = () => {
      setSegments(segments.map(s => s.id === segment.id ? { ...s, text: editText } : s));
      setIsEditing(false);
    };

    const handleKeyPress = (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && e.ctrlKey) {
        saveEdit();
      }
    };

    return (
      <div 
        className={`p-3 border rounded-lg cursor-pointer transition-all ${
          selectedSegments.has(segment.id)
            ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/50 dark:border-blue-400'
            : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
        } ${highlightedSegment?.id === segment.id ? 'ring-2 ring-yellow-400' : ''}`}
        onClick={() => !isEditing && handleSegmentClick(segment.id)}
      >
        <div className="flex items-center justify-between mb-2">
          <Badge variant="outline" className="text-xs">
            Segment {segment.id}
          </Badge>
          <div className="flex items-center gap-2">
            {segment.timestamp && (
              <Button
                size="sm"
                variant="ghost"
                onClick={(e) => {
                  e.stopPropagation();
                  seekTo(segment.timestamp!);
                }}
                className="text-xs h-6 px-2"
              >
                {segment.timestamp.start.toFixed(1)}s - {segment.timestamp.end.toFixed(1)}s
              </Button>
            )}
            <Button
              size="sm"
              variant="ghost"
              onClick={(e) => {
                e.stopPropagation();
                setIsEditing(!isEditing);
                if (!isEditing) setEditText(segment.text);
              }}
              className="text-xs h-6 px-2"
            >
              {isEditing ? 'Cancel' : 'Edit'}
            </Button>
          </div>
        </div>
        
        {isEditing ? (
          <div className="space-y-2">
            <textarea
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              onKeyPress={handleKeyPress}
              className="w-full p-2 rounded text-sm resize-none bg-transparent border-2 border-blue-500 text-inherit focus:outline-none focus:border-blue-400"
              rows={3}
              autoFocus
            />
            <div className="flex gap-2">
              <Button size="sm" onClick={saveEdit}>Save</Button>
              <Button 
                size="sm" 
                variant="outline"
                onClick={() => {
                  const position = Math.floor(editText.length / 2);
                  const beforeCursor = editText.substring(0, position);
                  const splitPos = beforeCursor.lastIndexOf(' ') !== -1 ? beforeCursor.lastIndexOf(' ') + 1 : position;
                  splitSegment(segment.id, splitPos);
                  setIsEditing(false);
                }}
              >
                <Split className="w-3 h-3 mr-1" />
                Split Here
              </Button>
            </div>
          </div>
        ) : (
          <p className="text-sm leading-relaxed">{segment.text}</p>
        )}
      </div>
    );
  };

  const getLanguageLabel = (code: string) => 
    languageOptions.find(l => l.value === code)?.label || code;

  const validateLanguagePair = (source: string, targets: string[]) => {
    const supportedPairs = Object.keys(LANGUAGE_PAIR_MODELS);
    return targets.every(target => supportedPairs.includes(`${source}-${target}`));
  };

  const handleTargetLanguageChange = (newTargets: string[]) => {
    if (sourceLanguage) {
      const validTargets = newTargets.filter(target => 
        validateLanguagePair(sourceLanguage, [target])
      );
      setTargetLanguages(validTargets);
    } else {
      setTargetLanguages(newTargets);
    }
    // Reset selected engines when targets change
    setSelectedEngines([]);
  };

  const getAvailableTargetLanguages = () => {
    if (!sourceLanguage) return languageOptions;
    
    return languageOptions.filter(lang => {
      if (lang.value === sourceLanguage) return false;
      return validateLanguagePair(sourceLanguage, [lang.value]);
    });
  };

  const handleEngineChange = (engine: string, checked: boolean) => {
    if (checked) {
      setSelectedEngines(prev => [...prev, engine]);
    } else {
      setSelectedEngines(prev => prev.filter(e => e !== engine));
    }
  };


  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">String Segmentation Editor</h1>
        <div className="flex gap-2">
          <Button onClick={onCancel} variant="outline">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Upload
          </Button>
          <Button
            onClick={mergeSelectedSegments}
            disabled={selectedSegments.size < 2}
            variant="outline"
          >
            <Merge className="w-4 h-4 mr-2" />
            Merge Selected ({selectedSegments.size})
          </Button>
          <Button onClick={() => setSelectedSegments(new Set())} variant="outline">
            Clear Selection
          </Button>
          <Button 
            onClick={handleSave} 
            disabled={isSaving || segments.length === 0 || targetLanguages.length === 0 || (useMultiEngine && selectedEngines.length === 0)}
            className="bg-blue-600 hover:bg-blue-700"
          >
            <Save className="w-4 h-4 mr-2" />
            {isSaving ? 'Processing...' : 'Save & Translate'}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              Original Media
              <Badge variant={mediaType === 'image' ? 'default' : 'secondary'}>
                {mediaType === 'image' ? 'Image' : 'Audio'}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
          {mediaType === 'image' ? (
            <div ref={imageContainerRef} className="relative bg-gray-100 dark:bg-gray-800 rounded-lg overflow-hidden" style={{ height: '400px' }}>
              {segmentationData?.mediaData && (
                <img
                  src={`data:image/png;base64,${segmentationData.mediaData}`}
                  alt="Original"
                  className="absolute inset-0 w-full h-full object-contain"
                  onLoad={(e) => {
                    const img = e.currentTarget;
                    setNaturalImageSize({ w: img.naturalWidth, h: img.naturalHeight });
                  }}
                />
              )}

              {!segmentationData?.mediaData && (
                <div className="absolute inset-0 bg-gradient-to-br from-blue-100 to-green-100 dark:from-blue-900/30 dark:to-green-900/30 flex items-center justify-center">
                  <p className="text-gray-500 dark:text-gray-400">Original Image Preview</p>
                </div>
              )}

              {/* Bounding boxes scaled to match object-contain rendering */}
              {naturalImageSize && segments.map((segment) => {
                if (!segment.bbox) return null;
                const container = imageContainerRef.current;
                if (!container) return null;
                const cw = container.clientWidth;
                const ch = container.clientHeight;
                const scale = Math.min(cw / naturalImageSize.w, ch / naturalImageSize.h);
                const displayW = naturalImageSize.w * scale;
                const displayH = naturalImageSize.h * scale;
                const offsetX = (cw - displayW) / 2;
                const offsetY = (ch - displayH) / 2;
                return (
                  <div
                    key={segment.id}
                    className={`absolute border-2 transition-all cursor-pointer ${
                      selectedSegments.has(segment.id)
                        ? 'border-blue-500 bg-blue-200/30'
                        : highlightedSegment?.id === segment.id
                        ? 'border-yellow-400 bg-yellow-200/30'
                        : 'border-red-500 hover:bg-red-200/20'
                    }`}
                    style={{
                      left: `${offsetX + segment.bbox.x * scale}px`,
                      top: `${offsetY + segment.bbox.y * scale}px`,
                      width: `${segment.bbox.w * scale}px`,
                      height: `${segment.bbox.h * scale}px`,
                    }}
                    onClick={() => handleSegmentClick(segment.id)}
                    onMouseEnter={() => setHighlightedSegment(segment)}
                    onMouseLeave={() => setHighlightedSegment(null)}
                  >
                    <span className="absolute -top-5 left-0 bg-black text-white text-xs px-1 rounded">
                      {segment.id}
                    </span>
                  </div>
                );
              })}
            </div>

            ) : (
              <div className="space-y-4">
                <audio 
                  ref={audioRef} 
                  hidden 
                  onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)} 
                  onEnded={() => setIsPlaying(false)}
                />

                <div className="h-32 bg-gray-100 dark:bg-gray-700 rounded-lg flex items-center justify-center relative overflow-hidden">
                  <div className="absolute inset-0 flex items-center">
                    {Array.from({length: 100}).map((_, i) => (
                      <div
                        key={i}
                        className="bg-blue-400 mx-px"
                        style={{
                          height: `${Math.random() * 60 + 10}%`,
                          width: '2px'
                        }}
                      />
                    ))}
                  </div>
                  <p className="text-gray-500 relative z-10">Audio Waveform</p>
                </div>
                
                <div className="flex items-center gap-4">
                  <Button
                    onClick={togglePlayback}
                    variant="outline"
                    size="sm"
                    disabled={!segmentationData?.mediaData}
                  >
                    {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                  </Button>
                  <div className="flex-1 bg-gray-200 rounded-full h-2 relative">
                    <div 
                      className="bg-blue-500 h-2 rounded-full transition-all"
                      style={{ width: `${(currentTime / duration) * 100}%` }}
                    />
                  </div>
                  <span className="text-sm text-gray-600">{currentTime.toFixed(1)}s / {duration.toFixed(1)}s</span>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Start of MODIFIED Right Column */}
        <div className="space-y-6">
        
          {/* === NEW CARD: TRANSLATION SETTINGS (Interactive) === */}
          <Card>
              <CardHeader>
                  <CardTitle>Translation Settings</CardTitle>
                  <p className="text-sm text-muted-foreground">Select target languages and translation models.</p>
              </CardHeader>
              <CardContent className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {/* Source Language Display (Read-only as it's detected) */}
                      <div>
                          <label className="block text-sm font-medium mb-2">Source Language</label>
                          <Badge className="w-full justify-center py-2 bg-blue-100 text-blue-800 text-sm font-semibold">
                              {getLanguageLabel(sourceLanguage)} (Detected)
                          </Badge>
                      </div>
                      
                      {/* Target Languages Selection (Editable) */}
                      <div>
                          <label className="block text-sm font-medium mb-2">
                              Target Languages
                          </label>
                          <MultiSelect
                              options={getAvailableTargetLanguages()}
                              selectedValues={targetLanguages}
                              onSelectionChange={handleTargetLanguageChange}
                              placeholder="Select target languages"
                          />
                          {targetLanguages.length > 0 && (
                            <p className="text-xs text-gray-500 mt-1">
                              Available pairs: {getAvailableTargetLanguages().map(l => l.label).join(', ')}
                            </p>
                          )}
                          {targetLanguages.length === 0 && (
                            <p className="text-xs text-red-500 mt-1">
                              Target languages required to translate.
                            </p>
                          )}
                      </div>
                  </div>

                  {/* Engine Configuration (Interactive) */}
                  {sourceLanguage && targetLanguages.length > 0 && (
                    <div className="space-y-4 p-4 border rounded-lg bg-blue-50 dark:bg-blue-900/20">
                      <div className="flex items-center space-x-2">
                          <Checkbox
                              id="multiEngine"
                              checked={useMultiEngine}
                              onCheckedChange={(checked) => setUseMultiEngine(checked as boolean)}
                          />
                          <label htmlFor="multiEngine" className="text-sm font-medium">
                              Use Multi-Model Translation
                          </label>
                          <Badge variant="outline" className="text-xs">
                              Compare {availableModels.length} Available Models
                          </Badge>
                      </div>
                      
                      {useMultiEngine && availableModels.length > 0 && (
                          <div className="space-y-3">
                              <p className="text-sm text-muted-foreground">
                                  Available models for {targetLanguages.map(t => `${sourceLanguage}→${t}`).join(', ')}:
                              </p>
                              <div className="space-y-3">
                                  {availableModels.map((model) => (
                                      <div key={model.id} className="flex items-start space-x-3 p-3 border rounded-md hover:bg-muted/50 transition-colors">
                                          <Checkbox
                                              id={model.id}
                                              checked={selectedEngines.includes(model.id)}
                                              onCheckedChange={(checked) => handleEngineChange(model.id, checked as boolean)}
                                              className="mt-1"
                                          />
                                          <div className="flex-1">
                                              <label htmlFor={model.id} className="text-sm font-medium flex items-center gap-2 cursor-pointer">
                                                  {model.label}
                                              </label>
                                              <p className="text-xs text-muted-foreground mt-1">
                                                  {model.description}
                                              </p>
                                              <p className="text-xs text-blue-600 mt-1">
                                                  Supports: {model.pairs.join(', ')}
                                              </p>
                                          </div>
                                      </div>
                                  ))}
                              </div>
                              {selectedEngines.length === 0 && (
                                  <p className="text-xs text-red-600">
                                      Please select at least one translation model.
                                  </p>
                              )}
                          </div>
                      )}
                      {!useMultiEngine && availableModels.length > 0 && (
                          <div className="text-xs text-muted-foreground">
                              Single model mode will use: {availableModels[0]?.label}
                          </div>
                      )}
                    </div>
                  )}
              </CardContent>
          </Card>
          {/* === END NEW CARD === */}

          {/* Existing Card: Text Segments */}
          <Card>
            <CardHeader>
              <CardTitle>
                Text Segments ({segments.length})
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                Click segments to select, edit text inline, or use controls to split/merge
              </p>
            </CardHeader>
            <CardContent>
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {segments.map((segment) => (
                  <EditableSegment key={segment.id} segment={segment} />
                ))}
              </div>
              
              <Separator className="my-4" />
              
              <div className="space-y-2">
                <h4 className="font-medium text-sm">Quick Actions:</h4>
                <div className="flex flex-wrap gap-2 text-xs text-gray-600">
                  <span>• Click segments to select multiple</span>
                  <span>• Click "Edit" to modify text</span>
                  <span>• Use "Split Here" to break long segments</span>
                  <span>• Select multiple and click "Merge" to combine</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
        {/* End of MODIFIED Right Column */}
      </div>

      <Card>
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold text-blue-600">{segments.length}</div>
              <div className="text-sm text-gray-600">Total Segments</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-green-600">
                {segments.reduce((acc, s) => acc + s.text.split(' ').length, 0)}
              </div>
              <div className="text-sm text-gray-600">Total Words</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-purple-600">{selectedSegments.size}</div>
              <div className="text-sm text-gray-600">Selected</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-orange-600">
                {segments.reduce((acc, s) => acc + s.text.length, 0)}
              </div>
              <div className="text-sm text-gray-600">Total Characters</div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

// ===== MAIN REQUEST TRANSLATION COMPONENT =====
export const RequestTranslation: React.FC = () => {
  const [sourceLanguage, setSourceLanguage] = useState<string>('');
  const [targetLanguages, setTargetLanguages] = useState<string[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [wordCount, setWordCount] = useState<number>(0);
  const [isProcessingFile, setIsProcessingFile] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submitStatus, setSubmitStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [isDetectingLanguage, setIsDetectingLanguage] = useState<boolean>(false);
  
  const [useMultiEngine, setUseMultiEngine] = useState(false);
  const [selectedEngines, setSelectedEngines] = useState<string[]>([]);

  const [showSegmentationEditor, setShowSegmentationEditor] = useState(false);
  const [segmentationData, setSegmentationData] = useState<any>(null);

  const availableModels = useMemo(() => {
    if (!sourceLanguage || targetLanguages.length === 0) return [];
    
    const allModels: Array<{id: string, label: string, icon?: string, description: string, pairs: string[]}> = [];
    
    targetLanguages.forEach(target => {
      const pair = `${sourceLanguage}-${target}`;
      const pairModels = LANGUAGE_PAIR_MODELS[pair as keyof typeof LANGUAGE_PAIR_MODELS] || [];
      
      pairModels.forEach(model => {
        const existingModel = allModels.find(m => m.id === model.id);
        if (existingModel) {
          existingModel.pairs.push(pair);
        } else {
          allModels.push({
            ...model,
            pairs: [pair]
          });
        }
      });
    });
    
    return allModels;
  }, [sourceLanguage, targetLanguages]);

  useEffect(() => {
    if (availableModels.length > 0 && selectedEngines.length === 0) {
      const defaultSelection = availableModels.map(m => m.id);
      setSelectedEngines(defaultSelection);
    }
  }, [availableModels, selectedEngines.length]);

  const countWords = (text: string, sourceLanguage?: string): number => {
    const isJapanese = sourceLanguage === 'JA' || /[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]/.test(text);
    
    if (isJapanese) {
      const cleanText = text.replace(/[\s.,!?。！？、]/g, '');
      return cleanText.length;
    }
    
    const words = text.trim().split(/\s+/).filter(word => word.length > 0);
    return words.length;
  };

  const extractTextFromFile = async (file: File): Promise<string> => {
    const fileType = file.type;
    
    if (fileType.includes('text/plain')) {
      const text = await file.text();
      return text.normalize('NFC');
    } else {
      return 'Content from non-text file types will be extracted on the backend.';
    }
  };

  const handleFilePreprocessing = async (uploadedFile: File) => {
    setIsProcessingFile(true);
    try {
      const formData = new FormData();
      formData.append('file', uploadedFile);
  
      const response = await fetch(`${API_BASE_URL}/api/translation-requests/file-preprocessing`, {
        method: 'POST',
        body: formData,
      });
  
      if (!response.ok) {
        throw new Error('Failed to preprocess file.');
      }
  
      const result = await response.json();
      
      if (result.success && result.segments && result.segments.length > 0) {
        setSegmentationData(result);
        
        // Only set source language here (detected)
        setSourceLanguage(result.detectedLanguage);
        
        setWordCount(result.wordCount);
        setShowSegmentationEditor(true);
      } else {
        alert('Audio transcription failed. Using standard processing.');
        await handleStandardLanguageDetection(uploadedFile);
      }
    } catch (error) {
      console.error('Error preprocessing file:', error);
      alert('Failed to preprocess file for segmentation. Using standard processing.');
      await handleStandardLanguageDetection(uploadedFile);
    } finally {
      setIsProcessingFile(false);
    }
  };

  const handleStandardLanguageDetection = async (uploadedFile: File) => {
    setIsDetectingLanguage(true);
    const formData = new FormData();
    formData.append('file', uploadedFile);

    try {
      const langResponse = await fetch(`${API_BASE_URL}/api/translation-requests/detect-language`, {
        method: 'POST',
        body: formData,
      });

      if (!langResponse.ok) throw new Error('Failed to detect language.');

      const langResult = await langResponse.json();
      const detectedLanguage = langResult.language;
      
      const supportedLang = languageOptions.find(l => l.value === detectedLanguage);

      if (supportedLang) {
        setSourceLanguage(supportedLang.value);
        const textContent = await extractTextFromFile(uploadedFile);
        setWordCount(countWords(textContent, supportedLang.value));
      } else {
        setSourceLanguage('');
        alert(`Detected language "${detectedLanguage}" is not supported. Please select the correct language manually.`);
      }
    } catch (error) {
      console.error('Error processing file:', error);
      alert(error instanceof Error ? error.message : "An unknown error occurred.");
      setSourceLanguage('');
    } finally {
      setIsDetectingLanguage(false);
    }
  };

  const handleFileUpload = async (event: { files: File[] }) => {
    const uploadedFile = event.files?.[0];
    if (!uploadedFile) return;

    setFile(uploadedFile);
    setWordCount(0);
    setSubmitStatus('idle');
    setSourceLanguage('');
    // Clear targets/engines when a new file is uploaded
    setTargetLanguages([]);
    setSelectedEngines([]);
    setUseMultiEngine(false);

    if (requiresSegmentation(uploadedFile.type)) {
      await handleFilePreprocessing(uploadedFile);
    } else {
      await handleStandardLanguageDetection(uploadedFile);
    }
  };

  const handleSegmentationSave = async (segmentationPayload: any) => {
    setIsSubmitting(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/translation-requests/segmentation/${segmentationData.segmentationId}/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(segmentationPayload),
      });

      if (!response.ok) throw new Error('Failed to save segmentation.');

      await response.json();
      setSubmitStatus('success');
      setShowSegmentationEditor(false);
      
      setTimeout(() => {
        setSourceLanguage('');
        setTargetLanguages([]);
        setFile(null);
        setWordCount(0);
        setSubmitStatus('idle');
        setUseMultiEngine(false);
        setSelectedEngines([]);
        setSegmentationData(null);
      }, 2000);
    } catch (error) {
      console.error('Error saving segmentation:', error);
      setSubmitStatus('error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSegmentationCancel = () => {
    setShowSegmentationEditor(false);
    setSegmentationData(null);
  };

  const validateLanguagePair = (source: string, targets: string[]) => {
    const supportedPairs = Object.keys(LANGUAGE_PAIR_MODELS);
    return targets.every(target => supportedPairs.includes(`${source}-${target}`));
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: (acceptedFiles) => handleFileUpload({ files: acceptedFiles }),
    accept: {
      'text/plain': ['.txt'],
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx', '.doc'],
      'image/*': ['.jpg', '.jpeg', '.png', '.gif'],
      'audio/*': ['.mp3', '.wav', '.flac']
    },
    multiple: false
  });
  
  // NOTE: These handlers are now unused in the main component but are passed to the editor
  const handleTargetLanguageChange = (newTargets: string[]) => {
    if (sourceLanguage) {
      const validTargets = newTargets.filter(target => 
        validateLanguagePair(sourceLanguage, [target])
      );
      setTargetLanguages(validTargets);
    } else {
      setTargetLanguages(newTargets);
    }
    setSelectedEngines([]);
  };

  const handleSourceLanguageChange = async (newSource: string) => {
    setSourceLanguage(newSource);
    if (file) {
      const textContent = await extractTextFromFile(file);
      setWordCount(countWords(textContent, newSource));
    }
    if (targetLanguages.length > 0) {
      const validTargets = targetLanguages.filter(target => 
        validateLanguagePair(newSource, [target])
      );
      setTargetLanguages(validTargets);
    }
    setSelectedEngines([]);
  };

  const handleEngineChange = (engine: string, checked: boolean) => {
    if (checked) {
      setSelectedEngines(prev => [...prev, engine]);
    } else {
      setSelectedEngines(prev => prev.filter(e => e !== engine));
    }
  };

  const handleSubmit = async () => {
    if (!sourceLanguage || targetLanguages.length === 0 || !file) return;
    
    setIsSubmitting(true);
    setSubmitStatus('idle');
    
    try {
      let endpoint = '';
      const formData = new FormData();
      formData.append('file', file);

      if (useMultiEngine) {
        endpoint = `${API_BASE_URL}/api/translation-requests/file-multi-engine`;
        formData.append('sourceLanguage', sourceLanguage);
        targetLanguages.forEach(lang => formData.append('targetLanguages', lang));
        selectedEngines.forEach(engine => formData.append('engines', engine));
      } else {
        endpoint = `${API_BASE_URL}/api/translation-requests/file-single-engine`;
        formData.append('sourceLanguage', sourceLanguage);
        targetLanguages.forEach(lang => formData.append('targetLanguages', lang));
      }

      console.log('Submitting file to:', endpoint);
      
      const response = await fetch(endpoint, {
        method: 'POST',
        body: formData,
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Server error:', errorText);
        throw new Error(`Failed to submit translation request: ${errorText}`);
      }
      
      const result = await response.json();
      setSubmitStatus('success');
      
      console.log('Translation request created:', result);
      
      setTimeout(() => {
        setSourceLanguage('');
        setTargetLanguages([]);
        setFile(null);
        setWordCount(0);
        setSubmitStatus('idle');
        setUseMultiEngine(false);
        setSelectedEngines([]);
      }, 2000);
      
    } catch (error) {
      console.error('Error submitting translation request:', error);
      setSubmitStatus('error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getAvailableTargetLanguages = () => {
    if (!sourceLanguage) return languageOptions;
    
    return languageOptions.filter(lang => {
      if (lang.value === sourceLanguage) return false;
      return validateLanguagePair(sourceLanguage, [lang.value]);
    });
  };

  if (showSegmentationEditor && segmentationData) {
    return (
      <SegmentationEditor
        segmentationData={segmentationData}
        onSave={handleSegmentationSave}
        onCancel={handleSegmentationCancel}
        
        // Pass all relevant state and setters to the editor
        sourceLanguage={sourceLanguage}
        setSourceLanguage={setSourceLanguage}
        targetLanguages={targetLanguages}
        setTargetLanguages={setTargetLanguages}
        useMultiEngine={useMultiEngine}
        setUseMultiEngine={setUseMultiEngine}
        selectedEngines={selectedEngines}
        setSelectedEngines={setSelectedEngines}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Request Translation</h1>
      </div>

      <Card className="max-w-2xl mx-auto">
        <CardHeader>
          <CardTitle>Create New Translation Request</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">
                Source Language
              </label>
              <Select value={sourceLanguage} onValueChange={handleSourceLanguageChange}>
                <SelectTrigger>
                  <SelectValue placeholder="Select source language" />
                </SelectTrigger>
                <SelectContent>
                  {languageOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            
            <div>
              <label className="block text-sm font-medium mb-2">
                Target Languages
              </label>
              <MultiSelect
                options={getAvailableTargetLanguages()}
                selectedValues={targetLanguages}
                onSelectionChange={handleTargetLanguageChange}
                placeholder="Select target languages"
              />
              {sourceLanguage && targetLanguages.length > 0 && (
                <p className="text-xs text-gray-500 mt-1">
                  Available pairs: {getAvailableTargetLanguages().map(l => l.label).join(', ')}
                </p>
              )}
            </div>
          </div>

          {sourceLanguage && targetLanguages.length > 0 && (
            <div className="space-y-4 p-4 border rounded-lg bg-blue-50 dark:bg-blue-900/20">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="multiEngine"
                  checked={useMultiEngine}
                  onCheckedChange={(checked) => setUseMultiEngine(checked as boolean)}
                />
                <label htmlFor="multiEngine" className="text-sm font-medium">
                  Use Multi-Model Translation
                </label>
                <Badge variant="outline" className="text-xs">
                  Compare {availableModels.length} Available Models
                </Badge>
              </div>
              
              {useMultiEngine && availableModels.length > 0 && (
                <div className="space-y-3">
                  <p className="text-sm text-muted-foreground">
                    Available models for {targetLanguages.map(t => `${sourceLanguage}→${t}`).join(', ')}:
                  </p>
                  <div className="space-y-3">
                    {availableModels.map((model) => (
                      <div key={model.id} className="flex items-start space-x-3 p-3 border rounded-md hover:bg-muted/50 transition-colors">
                        <Checkbox
                          id={model.id}
                          checked={selectedEngines.includes(model.id)}
                          onCheckedChange={(checked) => handleEngineChange(model.id, checked as boolean)}
                          className="mt-1"
                        />
                        <div className="flex-1">
                          <label htmlFor={model.id} className="text-sm font-medium flex items-center gap-2 cursor-pointer">
                            <span>{model.icon}</span>
                            {model.label}
                          </label>
                          <p className="text-xs text-muted-foreground mt-1">
                            {model.description}
                          </p>
                          <p className="text-xs text-blue-600 mt-1">
                            Supports: {model.pairs.join(', ')}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                  {selectedEngines.length === 0 && (
                    <p className="text-xs text-red-600">
                      Please select at least one translation model.
                    </p>
                  )}
                </div>
              )}

              {!useMultiEngine && availableModels.length > 0 && (
                <div className="text-xs text-muted-foreground">
                  Single model mode will use: {availableModels[0]?.label}
                </div>
              )}
            </div>
          )}
          
          <div>
            <label className="block text-sm font-medium mb-2">Upload File</label>
            <div 
              {...getRootProps()} 
              className={`p-6 border-2 border-dashed rounded-lg text-center cursor-pointer transition-colors
                         ${isDragActive ? 'bg-blue-50 dark:bg-blue-900/20 border-blue-500' : 'bg-gray-50 dark:bg-gray-800 border-gray-300 dark:border-gray-600'}`}
            >
              <input {...getInputProps()} />
              {isDetectingLanguage || isProcessingFile ? (
                <p className="text-blue-600">
                  {file && requiresSegmentation(file.type) 
                    ? "Processing media file and extracting segments..." 
                    : "Analyzing file and detecting language..."}
                </p>
              ) : isDragActive ? (
                <p>Drop the file here...</p>
              ) : file ? (
                <div>
                  <p>File "{file.name}" selected. Click or drag to change.</p>
                  {requiresSegmentation(file.type) && (
                    <p className="text-sm text-blue-600 mt-1">
                      This {file.type.startsWith('image/') ? 'image' : 'audio'} file will use advanced segmentation.
                    </p>
                  )}
                </div>
              ) : (
                <div>
                  <p>Drag 'n' drop a file here, or click to select a file</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                    Images and audio files will automatically open the segmentation editor
                  </p>
                </div>
              )}
            </div>
            {file && (
              <div className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                <p><strong>Selected:</strong> {file.name}</p>
                <p><strong>Size:</strong> {formatFileSize(file.size)}</p>
                <p><strong>Type:</strong> {file.type}</p>
                {isProcessingFile && (
                  <p className="text-blue-600">Processing file...</p>
                )}
              </div>
            )}
            <p className="mt-2 text-xs text-muted-foreground">
              Supported file types: .txt, .pdf, .docx, .mp3, .wav, .flac, .jpg, .png, .gif
            </p>
          </div>

          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-medium mb-2">Translation Summary</h3>
              <div className="text-sm text-gray-600 space-y-1">
                <p><strong>Source:</strong> {sourceLanguage ? languageOptions.find(l => l.value === sourceLanguage)?.label : 'Not selected'}</p>
                <p><strong>Targets:</strong> {targetLanguages.length > 0 ? targetLanguages.map(lang => languageOptions.find(l => l.value === lang)?.label).join(', ') : 'None selected'}</p>
                <p><strong>File:</strong> {file?.name || 'No file selected'}</p>
                {useMultiEngine && selectedEngines.length > 0 && (
                  <p><strong>Models:</strong> 
                    <span className="ml-1 text-purple-600">
                      {selectedEngines.map(engine => availableModels.find(m => m.id === engine)?.label).join(', ')}
                    </span>
                  </p>
                )}
                {file && (
                  <p><strong>Word Count:</strong> 
                    {isProcessingFile ? (
                      <span className="text-blue-600 ml-1">Calculating...</span>
                    ) : (
                      <span className="ml-1 font-semibold text-green-600">
                        {wordCount.toLocaleString()} {sourceLanguage === 'JA' ? 'characters' : 'words'}
                      </span>
                    )}
                  </p>
                )}
                {file && wordCount > 0 && targetLanguages.length > 0 && (
                  <p><strong>Total {sourceLanguage === 'JA' ? 'Characters' : 'Words'} to Translate:</strong> 
                    <span className="ml-1 font-semibold text-blue-600">
                      {(wordCount * targetLanguages.length * (useMultiEngine ? selectedEngines.length : 1)).toLocaleString()} {sourceLanguage === 'JA' ? 'characters' : 'words'}
                    </span>
                  </p>
                )}
                {sourceLanguage && targetLanguages.length > 0 && (
                  <p><strong>Language Pairs:</strong> 
                    <span className="ml-1 text-purple-600">
                      {targetLanguages.map(target => `${sourceLanguage}-${target}`).join(', ')}
                    </span>
                  </p>
                )}
              </div>
            </div>
          </div>

          {submitStatus === 'success' && (
            <div className="p-3 bg-green-100 border border-green-400 text-green-700 rounded">
              Translation request submitted successfully! Form will reset shortly.
            </div>
          )}

          {submitStatus === 'error' && (
            <div className="p-3 bg-red-100 border border-red-400 text-red-700 rounded">
              Failed to submit translation request. Please try again.
            </div>
          )}

          <Button 
            className="w-full" 
            onClick={handleSubmit}
            disabled={
              !sourceLanguage || 
              targetLanguages.length === 0 || 
              !file || 
              isProcessingFile || 
              isSubmitting ||
              isDetectingLanguage ||
              (useMultiEngine && selectedEngines.length === 0)
            }
          >
            {isSubmitting ? 'Submitting...' : 
             isDetectingLanguage || isProcessingFile ? 'Processing File...' :
             useMultiEngine ? `Submit Multi-Model Translation (${selectedEngines.length} models)` :
             'Submit Translation Request'}
          </Button>

          <Card className="mt-6">
            <CardHeader>
              <CardTitle>WMT Benchmark Testing</CardTitle>
              <p className="text-sm text-muted-foreground">
                Test with professional WMT datasets for standardized evaluation using local models
              </p>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { pair: "jpn-eng", label: "JA→EN" },
                  { pair: "eng-jpn", label: "EN→JA" },
                  { pair: "eng-fra", label: "EN→FR" },
                  { pair: "fra-eng", label: "FR→EN" },
                  { pair: "jpn-fra", label: "JA→FR (Pivot)" }
                ].map(({ pair, label }) => (
                  <Button 
                    key={pair}
                    variant="outline"
                    onClick={async () => {
                      try {
                        const response = await fetch(`${API_BASE_URL}/api/wmt/create-request?language_pair=${pair}&sample_size=10`, {
                          method: 'POST'
                        });
                        if (response.ok) {
                          alert(`WMT ${label} test created!`);
                        } else {
                          const error = await response.text();
                          alert(`Failed to create ${label} test: ${error}`);
                        }
                      } catch (error) {
                        console.error('Failed to create WMT request:', error);
                        alert(`Error creating ${label} test`);
                      }
                    }}
                  >
                    Test {label}
                  </Button>
                ))}
              </div>
            </CardContent>
          </Card>
        </CardContent>
      </Card>
    </div>
  );
};

export default RequestTranslation;