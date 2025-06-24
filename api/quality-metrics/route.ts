// api/quality-metrics/calculate/route.ts
import { NextRequest } from 'next/server';
import { QualityMetricsService } from '../../../services/QualityMetricsService.js';

export async function POST(request: NextRequest) {
  try {
    const { requestId } = await request.json();
    
    const qualityService = new QualityMetricsService();
    await qualityService.calculateMetricsForRequest(requestId);
    
    return Response.json({ success: true });
  } catch (error) {
    console.error('Quality metrics calculation error:', error);
    return Response.json(
      { error: 'Failed to calculate quality metrics' }, 
      { status: 500 }
    );
  }
}
