import { Stack, StackProps, RemovalPolicy, CfnOutput, Duration } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { aws_s3 as s3, aws_lambda as lambda, aws_apigateway, aws_dynamodb as dynamodb, aws_iam as iam} from 'aws-cdk-lib';
import * as path from 'path';
// import {config} from 'dotenv';
// config();

export class FairshareBackendStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    const receiptImageBucket = "fairshare-receipt-image-bucket"
    new s3.Bucket(this, "ReceiptImageBucket", {
        bucketName: receiptImageBucket,
        publicReadAccess: true,
        blockPublicAccess: {
          blockPublicAcls: false,
          blockPublicPolicy: false,
          ignorePublicAcls: false,
          restrictPublicBuckets: false,
        },
        removalPolicy: RemovalPolicy.DESTROY,
        cors: [
            {
                allowedMethods: [
                    s3.HttpMethods.GET,
                    s3.HttpMethods.POST,
                    s3.HttpMethods.PUT,
                    s3.HttpMethods.DELETE
                ],
                allowedOrigins: ['*'],
                allowedHeaders: ['*']
            }
        ]
    });

    const receiptTable = new dynamodb.Table(this, "ReceiptTable", {
        partitionKey: { name: 'id', type: dynamodb.AttributeType.STRING },
        tableName: 'receipts',
        billingMode: dynamodb.BillingMode.PAY_PER_REQUEST
    });

    const itemsTable = new dynamodb.Table(this, 'ItemsTable', {
      partitionKey: { name: 'id', type: dynamodb.AttributeType.STRING },
      tableName: 'items',
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
    });

    // Create the Users table
    const usersTable = new dynamodb.Table(this, 'UsersTable', {
        partitionKey: { name: 'id', type: dynamodb.AttributeType.STRING },
        tableName: 'users',
        billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
    });

    // Create the Splits table
    const splitsTable = new dynamodb.Table(this, 'SplitsTable', {
        partitionKey: { name: 'id', type: dynamodb.AttributeType.STRING },
        tableName: 'splits',
        billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
    });

    // Add GSI to the splits and items tables
    itemsTable.addGlobalSecondaryIndex({
        indexName: 'itemsByReceiptId',
        partitionKey: { name: 'receipt_id', type: dynamodb.AttributeType.STRING },
        sortKey: { name: 'id', type: dynamodb.AttributeType.STRING },
    });
    splitsTable.addGlobalSecondaryIndex({
        indexName: 'splitsByReceiptId',
        partitionKey: { name: 'receipt_id', type: dynamodb.AttributeType.STRING },
        sortKey: { name: 'id', type: dynamodb.AttributeType.STRING },
    });

    const api = new aws_apigateway.RestApi(this, "ReceiptApi", {
        restApiName: 'Receipt API',
        description: 'This service serves receipts.',
        defaultCorsPreflightOptions: {
            allowOrigins: aws_apigateway.Cors.ALL_ORIGINS,
            allowMethods: aws_apigateway.Cors.ALL_METHODS,
            allowHeaders: ['Content-Type', 'X-Amz-Date', 'Authorization', 'X-Api-Key', 'X-Amz-Security-Token'],
        }
    });

    const sharedRole = new iam.Role(this, 'SharedLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
          iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
          iam.ManagedPolicy.fromAwsManagedPolicyName('AmazonS3FullAccess'),
      ],
    });

    const rootHandlerLambda = new lambda.Function(this, "HealthLambda", {
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: 'app.hello_lambda',
      code: lambda.Code.fromAsset(path.join(__dirname, '../backend')),
      role: sharedRole,
    });

    const presignedUrlLambda = new lambda.Function(this, "PresignedUrlLambda", {
        runtime: lambda.Runtime.PYTHON_3_9,
        handler: 'app.presigned_url_lambda',
        code: lambda.Code.fromAsset(path.join(__dirname, '../backend')),
        environment: {
            BUCKET_NAME: receiptImageBucket,
            APP_AWS_REGION: process.env.APP_AWS_REGION || '',
        },
        role: sharedRole,
    });
    
    const ocrLambda = new lambda.Function(this, "OcrLambda", {
        runtime: lambda.Runtime.PYTHON_3_8,
        handler: 'app.ocr_lambda',
        code: lambda.Code.fromAsset(path.join(__dirname, '../backend')),
        environment: {
            BUCKET_NAME: receiptImageBucket,
            APP_AWS_REGION: process.env.APP_AWS_REGION || '',
        },
        role: sharedRole,
        timeout: Duration.seconds(30)
    });
    
    const receiptHandlerLamdba = new lambda.Function(this, "ReceiptLambda", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: 'app.receipt_db_lambda',
      code: lambda.Code.fromAsset(path.join(__dirname, '../backend')),
      timeout: Duration.seconds(30),
      role: sharedRole,
    });

    const userHandlerLamdba = new lambda.Function(this, "UserLambda", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: 'app.user_db_lambda',
      code: lambda.Code.fromAsset(path.join(__dirname, '../backend')),
      timeout: Duration.seconds(30),
      role: sharedRole,
    });

    const allItemHandlerLamdba = new lambda.Function(this, "AllItemLambda", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: 'app.all_items_db_lambda',
      code: lambda.Code.fromAsset(path.join(__dirname, '../backend')),
      timeout: Duration.seconds(30),
      role: sharedRole,
    });

    const itemHandlerLamdba = new lambda.Function(this, "ItemLambda", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: 'app.item_db_lambda',
      code: lambda.Code.fromAsset(path.join(__dirname, '../backend')),
      timeout: Duration.seconds(30),
      role: sharedRole,
    });

    const allSplitHandlerLamdba = new lambda.Function(this, "AllSplitLambda", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: 'app.all_splits_db_lambda',
      code: lambda.Code.fromAsset(path.join(__dirname, '../backend')),
      timeout: Duration.seconds(30),
      role: sharedRole,
    });

    const splitHandlerLamdba = new lambda.Function(this, "SplitLambda", {
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: 'app.split_db_lambda',
      code: lambda.Code.fromAsset(path.join(__dirname, '../backend')),
      timeout: Duration.seconds(30),
      role: sharedRole,
    });

    receiptTable.grantReadWriteData(receiptHandlerLamdba);
    receiptTable.grantReadWriteData(ocrLambda);
    usersTable.grantReadWriteData(userHandlerLamdba);
    itemsTable.grantReadWriteData(allItemHandlerLamdba);
    itemsTable.grantReadWriteData(itemHandlerLamdba);
    splitsTable.grantReadWriteData(allSplitHandlerLamdba);
    splitsTable.grantReadWriteData(splitHandlerLamdba);


    const rootIntegration = new aws_apigateway.LambdaIntegration(rootHandlerLambda);
    const presignedUrlIntegration = new aws_apigateway.LambdaIntegration(presignedUrlLambda);
    const ocrIntegration = new aws_apigateway.LambdaIntegration(ocrLambda);
    const receiptIntegration = new aws_apigateway.LambdaIntegration(receiptHandlerLamdba);
    const userIntegration = new aws_apigateway.LambdaIntegration(userHandlerLamdba);
    const allItemIntegration = new aws_apigateway.LambdaIntegration(allItemHandlerLamdba);
    const itemIntegration = new aws_apigateway.LambdaIntegration(itemHandlerLamdba);
    const allSplitIntegration = new aws_apigateway.LambdaIntegration(allSplitHandlerLamdba);
    const splitIntegration = new aws_apigateway.LambdaIntegration(splitHandlerLamdba);

    
    const ocrResource = api.root.addResource('ocr');
    ocrResource.addMethod('POST', ocrIntegration, { 
      methodResponses: [{ statusCode: '200' }]
    });
    
    const presignedUrlResource = api.root.addResource('presigned-url');
    presignedUrlResource.addMethod('POST', presignedUrlIntegration, { 
      methodResponses: [{ statusCode: '200' }]
    });

    const receiptResource = api.root.addResource('receipt');
    receiptResource.addMethod('GET', receiptIntegration, { 
      methodResponses: [{ statusCode: '200' }]
    });
    receiptResource.addMethod('POST', receiptIntegration, {
      methodResponses: [{ statusCode: '200' }]
    });
    receiptResource.addMethod('PUT', receiptIntegration, {
      methodResponses: [{ statusCode: '200' }]
    });
    receiptResource.addMethod('DELETE', receiptIntegration, {
      methodResponses: [{ statusCode: '200' }]
    });

    const userResource = api.root.addResource('user');
    userResource.addMethod('GET', userIntegration, { 
      methodResponses: [{ statusCode: '200' }]
    });
    userResource.addMethod('POST', userIntegration, {
      methodResponses: [{ statusCode: '200' }]
    });
    userResource.addMethod('PUT', userIntegration, {
      methodResponses: [{ statusCode: '200' }]
    });
    userResource.addMethod('DELETE', userIntegration, {
      methodResponses: [{ statusCode: '200' }]
    });

    const allItemResource = api.root.addResource('allitem');
    allItemResource.addMethod('GET', allItemIntegration, {
      methodResponses: [{ statusCode: '200' }]
    });

    const itemResource = api.root.addResource('item');
    itemResource.addMethod('GET', itemIntegration, {
      methodResponses: [{ statusCode: '200' }]
    });
    itemResource.addMethod('POST', itemIntegration, {
      methodResponses: [{ statusCode: '200' }]
    });
    itemResource.addMethod('PUT', itemIntegration, {
      methodResponses: [{ statusCode: '200' }]
    });
    itemResource.addMethod('DELETE', itemIntegration, {
      methodResponses: [{ statusCode: '200' }]
    });

    const allSplitResource = api.root.addResource('allsplit');
    allSplitResource.addMethod('GET', allSplitIntegration, {
      methodResponses: [{ statusCode: '200' }]
    });

    const splitResource = api.root.addResource('split');
    splitResource.addMethod('GET', splitIntegration, {
      methodResponses: [{ statusCode: '200' }]
    });
    splitResource.addMethod('POST', splitIntegration, {
      methodResponses: [{ statusCode: '200' }]
    });
    splitResource.addMethod('PUT', splitIntegration, {
      methodResponses: [{ statusCode: '200' }]
    });
    splitResource.addMethod('DELETE', splitIntegration, {
      methodResponses: [{ statusCode: '200' }]
    });

    api.root.addMethod('GET', rootIntegration, { 
      methodResponses: [{ statusCode: '200' }]
    });

    new CfnOutput(this, 'ApiUrl', {
        value: api.url
    });
  }
}