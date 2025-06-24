// services/ModelManager.ts
import { MTModel, PrismaClient } from '@prisma/client';
import { spawn } from 'child_process';
import path from 'path';

export class ModelManager {
  private prisma = new PrismaClient();
  private modelBasePath = './models';

  private modelConfigs = {
    MARIAN_MT_EN_FR: "Helsinki-NLP/opus-mt-en-fr",
    MARIAN_MT_FR_EN: "Helsinki-NLP/opus-mt-fr-en", 
    MARIAN_MT_EN_JP: "Helsinki-NLP/opus-mt-en-jap",
    ELAN_MT_JP_EN: "Mitsua/elan-mt-bt-ja-en",
    T5_MULTILINGUAL: "google-t5/t5-base"
  };

  async downloadModel(modelType: MTModel): Promise<void> {
    const modelName = this.modelConfigs[modelType];
    
    return new Promise((resolve, reject) => {
      // Use Python script to download models
      const pythonScript = spawn('python', [
        'scripts/download_model.py',
        modelName,
        this.modelBasePath
      ]);

      pythonScript.on('close', async (code) => {
        if (code === 0) {
          await this.updateDatabase(modelType, modelName);
          resolve();
        } else {
          reject(new Error(`Model download failed with code ${code}`));
        }
      });
    });
  }

  private async updateDatabase(modelType: MTModel, modelName: string): Promise<void> {
    const modelPath = path.join(this.modelBasePath, modelName.replace('/', '_'));
    
    await this.prisma.localModel.upsert({
      where: { modelName },
      update: {
        isDownloaded: true,
        modelPath: modelPath
      },
      create: {
        modelName,
        modelType,
        sourceLanguage: this.getSourceLanguage(modelType),
        targetLanguage: this.getTargetLanguage(modelType),
        isDownloaded: true,
        modelPath: modelPath
      }
    });
  }

  private getSourceLanguage(modelType: MTModel): string {
    const mapping = {
      MARIAN_MT_EN_FR: 'EN',
      MARIAN_MT_FR_EN: 'FR',
      MARIAN_MT_EN_JP: 'EN',
      ELAN_MT_JP_EN: 'JP',
      T5_MULTILINGUAL: 'EN'
    };
    return mapping[modelType] || 'EN';
  }

  private getTargetLanguage(modelType: MTModel): string {
    const mapping = {
      MARIAN_MT_EN_FR: 'FR',
      MARIAN_MT_FR_EN: 'EN',
      MARIAN_MT_EN_JP: 'JP',
      ELAN_MT_JP_EN: 'EN',
      T5_MULTILINGUAL: 'FR'
    };
    return mapping[modelType] || 'EN';
  }
}
