// Add to src/utils/fuzzyMatch.ts
export const calculateFuzzyMatch = (sourceText: string, matchedText: string): number => {
    // Simple fuzzy matching algorithm based on character similarity
    const maxLength = Math.max(sourceText.length, matchedText.length);
    const minLength = Math.min(sourceText.length, matchedText.length);
    
    let matches = 0;
    for (let i = 0; i < minLength; i++) {
      if (sourceText.toLowerCase()[i] === matchedText.toLowerCase()[i]) {
        matches++;
      }
    }
    
    return Math.round((matches / maxLength) * 100);
  };
  
  export const getFuzzyMatchColor = (percentage: number): string => {
    if (percentage >= 95) return 'text-green-600';
    if (percentage >= 80) return 'text-blue-600';
    if (percentage >= 70) return 'text-yellow-600';
    if (percentage >= 50) return 'text-orange-600';
    return 'text-red-600';
  };
  
  export const getFuzzyMatchBadge = (percentage: number) => {
    if (percentage >= 95) return 'default';
    if (percentage >= 80) return 'secondary';
    if (percentage >= 70) return 'outline';
    return 'destructive';
  };
  