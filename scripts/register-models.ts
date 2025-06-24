// scripts/register-models.ts
import { MTModel, PrismaClient } from '@prisma/client';
import fs from 'fs/promises';
import path from 'path';

async function registerDownloadedModels() {
  const prisma = new PrismaClient();
  
  const modelConfigs = [
    {
      modelType: 'MARIAN_MT_EN_FR' as MTModel,
      modelName: 'Helsinki-NLP/opus-mt-en-fr',
      sourceLanguage: 'EN',
      targetLanguage: 'FR',
      modelPath: './models/Helsinki-NLP_opus-mt-en-fr'
    },
    {
      modelType: 'MARIAN_MT_FR_EN' as MTModel,
      modelName: 'Helsinki-NLP/opus-mt-fr-en',
      sourceLanguage: 'FR',
      targetLanguage: 'EN',
      modelPath: './models/Helsinki-NLP_opus-mt-fr-en'
    },
    {
      modelType: 'MARIAN_MT_EN_JP' as MTModel,
      modelName: 'Helsinki-NLP/opus-mt-en-jap',
      sourceLanguage: 'EN',
      targetLanguage: 'JP',
      modelPath: './models/Helsinki-NLP_opus-mt-en-jap'
    },
    {
      modelType: 'ELAN_MT_JP_EN' as MTModel,
      modelName: 'Mitsua/elan-mt-bt-ja-en',
      sourceLanguage: 'JP',
      targetLanguage: 'EN',
      modelPath: './models/Mitsua_elan-mt-bt-ja-en'
    },
    {
      modelType: 'T5_MULTILINGUAL' as MTModel,
      modelName: 'google-t5/t5-base',
      sourceLanguage: 'EN',
      targetLanguage: 'FR',
      modelPath: './models/google-t5_t5-base'
    }
  ];

  for (const config of modelConfigs) {
    const modelSize = await getDirectorySize(config.modelPath);
    
    await prisma.localModel.upsert({
      where: { modelName: config.modelName },
      update: {
        isDownloaded: true,
        modelPath: config.modelPath,
        modelSize: modelSize
      },
      create: {
        modelName: config.modelName,
        modelType: config.modelType,
        sourceLanguage: config.sourceLanguage,
        targetLanguage: config.targetLanguage,
        isDownloaded: true,
        modelPath: config.modelPath,
        modelSize: modelSize
      }
    });
    
    console.log(`✓ Registered ${config.modelName}`);
  }
  
  await prisma.$disconnect();
}

async function getDirectorySize(dirPath: string): Promise<number> {
  const stats = await fs.stat(dirPath);
  if (stats.isFile()) return Math.round(stats.size / (1024 * 1024));
  
  const files = await fs.readdir(dirPath);
  let totalSize = 0;
  
  for (const file of files) {
    const filePath = path.join(dirPath, file);
    const fileStats = await fs.stat(filePath);
    totalSize += fileStats.size;
  }
  
  return Math.round(totalSize / (1024 * 1024)); // Convert to MB
}

registerDownloadedModels();
