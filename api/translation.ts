// api/translation.ts
import { QualityMetricsService } from '../services/QualityMetricsService.js';
import { TranslationService } from '../services/TranslationService.js';

export async function POST(request: Request) {
  const translationService = new TranslationService();
  const qualityService = new QualityMetricsService();
  
  try {
    const { requestId, referenceText } = await request.json();
    
    // Process translation
    await translationService.processTranslationRequest(requestId);
    
    // Calculate quality metrics if reference provided
    if (referenceText) {
      const translationStrings = await prisma.translationString.findMany({
        where: { translationRequestId: requestId }
      });
      
      for (const string of translationStrings) {
        await qualityService.calculateMetrics(string.id, referenceText);
      }
    }
    
    return Response.json({ success: true });
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
}
