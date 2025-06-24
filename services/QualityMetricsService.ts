// services/QualityMetricsService.ts
import { PrismaClient } from '@prisma/client';
import { spawn } from 'child_process';

export class QualityMetricsService {
  private prisma = new PrismaClient();

  async calculateAllMetrics(translationStringId: string, referenceText?: string): Promise<void> {
    const translationString = await this.prisma.translationString.findUnique({
      where: { id: translationStringId }
    });

    if (!translationString) return;

    // Compute real metrics from quality_metrics.py (only if reference text is available)
    const realMetrics = referenceText ? await this.computeRealMetrics(
      translationString.translatedText, 
      referenceText
    ) : null;

    // Compute MetricX score from metricx_service.py (works with or without reference)
    const metricXResult = await this.computeMetricXScore(
      translationString.sourceText,
      translationString.translatedText,
      referenceText
    );

    // Determine overall quality label
    const qualityLabel = this.determineOverallQuality(realMetrics, metricXResult);

    // Store all metrics in database
    await this.prisma.qualityMetrics.create({
      data: {
        translationStringId,
        bleuScore: realMetrics?.bleu_score || null,
        terScore: realMetrics?.ter_score || null,
        cometScore: realMetrics?.chrf_score || null, // Using chrF as COMET placeholder
        metricXScore: metricXResult.score,
        metricXConfidence: metricXResult.confidence,
        metricXMode: this.mapMetricXMode(metricXResult.mode),
        metricXVariant: this.mapMetricXVariant(metricXResult.variant),
        qualityLabel: qualityLabel as any
      }
    });
  }

  // Keep the original method for backward compatibility
  async calculateMetrics(translationStringId: string, referenceText?: string): Promise<void> {
    return this.calculateAllMetrics(translationStringId, referenceText);
  }

  private async computeRealMetrics(hypothesis: string, reference: string): Promise<any> {
    return new Promise((resolve, reject) => {
      const pythonProcess = spawn('python', [
        'backend/quality_metrics.py',
        hypothesis,
        reference
      ]);

      let output = '';
      let errorOutput = '';

      pythonProcess.stdout.on('data', (data) => {
        output += data.toString();
      });

      pythonProcess.stderr.on('data', (data) => {
        errorOutput += data.toString();
      });

      pythonProcess.on('close', (code) => {
        if (code === 0) {
          try {
            const result = JSON.parse(output.trim());
            resolve(result);
          } catch (error) {
            reject(new Error(`Failed to parse metrics result: ${error.message}`));
          }
        } else {
          reject(new Error(`Metrics calculation failed with code ${code}: ${errorOutput}`));
        }
      });
    });
  }

  private async computeMetricXScore(source: string, hypothesis: string, reference?: string): Promise<any> {
    return new Promise((resolve, reject) => {
      // Create a temporary Python script to call the MetricX service
      const pythonScript = `
import sys
sys.path.append('backend')
from metricx_service import metricx_service
import json

source = """${source.replace(/"/g, '\\"')}"""
hypothesis = """${hypothesis.replace(/"/g, '\\"')}"""
reference = """${reference ? reference.replace(/"/g, '\\"') : ''}"""

result = metricx_service.evaluate_translation(
    source=source,
    hypothesis=hypothesis,
    reference=reference if reference else None
)

print(json.dumps(result))
`;

      const pythonProcess = spawn('python', ['-c', pythonScript]);

      let output = '';
      let errorOutput = '';

      pythonProcess.stdout.on('data', (data) => {
        output += data.toString();
      });

      pythonProcess.stderr.on('data', (data) => {
        errorOutput += data.toString();
      });

      pythonProcess.on('close', (code) => {
        if (code === 0) {
          try {
            const result = JSON.parse(output.trim());
            resolve(result);
          } catch (error) {
            reject(new Error(`Failed to parse MetricX result: ${error.message}`));
          }
        } else {
          reject(new Error(`MetricX calculation failed with code ${code}: ${errorOutput}`));
        }
      });
    });
  }

  private mapMetricXMode(mode: string): 'REFERENCE_BASED' | 'REFERENCE_FREE' {
    return mode.toLowerCase().includes('reference-based') ? 'REFERENCE_BASED' : 'REFERENCE_FREE';
  }

  private mapMetricXVariant(variant: string): 'METRICX_24_HYBRID' | 'METRICX_24_XL' | 'METRICX_24_XXL' {
    const normalized = variant.toUpperCase().replace(/-/g, '_');
    if (normalized.includes('HYBRID')) return 'METRICX_24_HYBRID';
    if (normalized.includes('XXL')) return 'METRICX_24_XXL';
    if (normalized.includes('XL')) return 'METRICX_24_XL';
    return 'METRICX_24_HYBRID'; // Default fallback
  }

  private determineOverallQuality(realMetrics: any, metricXResult: any): 'EXCELLENT' | 'GOOD' | 'FAIR' | 'POOR' {
    // Priority 1: Use MetricX quality level if available
    if (metricXResult && metricXResult.quality_level) {
      switch (metricXResult.quality_level.toLowerCase()) {
        case 'excellent':
          return 'EXCELLENT';
        case 'good':
          return 'GOOD';
        case 'fair':
          return 'FAIR';
        case 'poor':
          return 'POOR';
      }
    }

    // Priority 2: Use real metrics quality label if available
    if (realMetrics && realMetrics.quality_label) {
      return realMetrics.quality_label.toUpperCase() as 'EXCELLENT' | 'GOOD' | 'FAIR' | 'POOR';
    }

    // Priority 3: Fallback based on MetricX score (lower is better for MetricX)
    if (metricXResult && metricXResult.score) {
      const score = metricXResult.score;
      if (score <= 7) return 'EXCELLENT';
      if (score <= 12) return 'GOOD';
      if (score <= 18) return 'FAIR';
      return 'POOR';
    }

    // Default fallback
    return 'POOR';
  }

  // Utility method to calculate metrics for a batch of translation strings
  async calculateMetricsForRequest(requestId: string, referenceTexts?: string[]): Promise<void> {
    const translationStrings = await this.prisma.translationString.findMany({
      where: { translationRequestId: requestId }
    });

    for (let i = 0; i < translationStrings.length; i++) {
      const translationString = translationStrings[i];
      const referenceText = referenceTexts?.[i];
      
      try {
        await this.calculateAllMetrics(translationString.id, referenceText);
      } catch (error) {
        console.error(`Failed to calculate metrics for string ${translationString.id}:`, error);
      }
    }
  }
}
