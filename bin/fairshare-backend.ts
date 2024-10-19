#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { FairshareBackendStack } from '../lib/fairshare-backend-stack';

const app = new cdk.App();
new FairshareBackendStack(app, 'FairshareBackendStack', {
  env: { account: '682307583837', region: 'us-east-1' },
});