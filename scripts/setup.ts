// scripts/setup.ts
import { PrismaClient } from '@prisma/client';
import { ModelManager } from '../services/ModelManager.js';

async function setupSystem() {
  const prisma = new PrismaClient();
  const modelManager = new ModelManager();

  console.log('Starting system setup...');

  try {
    // Download all models
    console.log('Downloading models...');
    await modelManager.downloadAllModels();

    console.log('Setup completed successfully!');
  } catch (error) {
    console.error('Setup failed:', error);
  } finally {
    await prisma.$disconnect();
  }
}

setupSystem();
