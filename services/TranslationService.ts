// services/TranslationService.ts
import { PrismaClient } from '@prisma/client';
import { spawn } from 'child_process';

export class TranslationService {
  private prisma = new PrismaClient();

  async processTranslationRequest(requestId: string): Promise<void> {
    const request = await this.prisma.translationRequest.findUnique({
      where: { id: requestId },
      include: { translationStrings: true }
    });

    if (!request) throw new Error('Translation request not found');

    await this.prisma.translationRequest.update({
      where: { id: requestId },
      data: { status: 'IN_PROGRESS' }
    });

    const localModel = await this.prisma.localModel.findFirst({
      where: { modelType: request.mtModel, isDownloaded: true }
    });

    if (!localModel) {
      throw new Error(`Model ${request.mtModel} not available`);
    }

    for (const translationString of request.translationStrings) {
      const startTime = Date.now();
      
      try {
        const translation = await this.translateText(
          translationString.sourceText,
          localModel.modelName,
          localModel.modelPath!
        );
        
        const processingTime = Date.now() - startTime;

        await this.prisma.translationString.update({
          where: { id: translationString.id },
          data: {
            translatedText: translation,
            processingTimeMs: processingTime,
            status: 'REVIEWED'
          }
        });
      } catch (error) {
        console.error(`Translation failed for string ${translationString.id}:`, error);
      }
    }

    await this.prisma.translationRequest.update({
      where: { id: requestId },
      data: { status: 'COMPLETED' }
    });
  }

  private async translateText(text: string, modelName: string, modelPath: string): Promise<string> {
    return new Promise((resolve, reject) => {
      const pythonProcess = spawn('python', [
        'backend/translation_service.py',
        text,
        modelName,
        modelPath
      ]);

      let output = '';
      pythonProcess.stdout.on('data', (data) => {
        output += data.toString();
      });

      pythonProcess.on('close', (code) => {
        if (code === 0) {
          try {
            const result = JSON.parse(output.trim());
            resolve(result.translation);
          } catch (error) {
            reject(new Error('Failed to parse translation result'));
          }
        } else {
          reject(new Error(`Translation process failed with code ${code}`));
        }
      });
    });
  }
}
