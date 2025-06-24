// api/translation-requests/route.ts
import { PrismaClient } from '@prisma/client';
import { NextRequest } from 'next/server';

const prisma = new PrismaClient();

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const include = searchParams.get('include');
    
    const includeOptions: any = {};
    if (include?.includes('strings')) {
      includeOptions.translationStrings = true;
    }
    if (include?.includes('metrics')) {
      includeOptions.qualityMetrics = true;
    }
    
    const requests = await prisma.translationRequest.findMany({
      include: includeOptions,
      orderBy: {
        requestDate: 'desc'
      }
    });
    
    return Response.json(requests);
  } catch (error) {
    console.error('API Error:', error);
    return Response.json(
      { error: 'Failed to fetch translation requests' }, 
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const data = await request.json();
    
    const newRequest = await prisma.translationRequest.create({
      data: {
        sourceLanguage: data.sourceLanguage,
        targetLanguages: data.targetLanguages,
        languagePair: data.languagePair,
        wordCount: data.wordCount,
        fileName: data.fileName,
        mtModel: data.mtModel,
        translationStrings: {
          create: data.sourceTexts?.map((text: string) => ({
            sourceText: text,
            translatedText: '', // Will be filled by translation service
            targetLanguage: data.targetLanguages[0],
            status: 'DRAFT'
          })) || []
        }
      },
      include: {
        translationStrings: true
      }
    });
    
    return Response.json(newRequest);
  } catch (error) {
    console.error('API Error:', error);
    return Response.json(
      { error: 'Failed to create translation request' }, 
      { status: 500 }
    );
  }
}
