param location string = resourceGroup().location
param storageAccountName string
param containerEnvironmentName string
param acrName string
param appIdentityName string
param appIdentityClientId string
@secure()
param databaseUrl string
param apiImage string
param workerImage string

resource storage 'Microsoft.Storage/storageAccounts@2025-06-01' existing = { name: storageAccountName }
resource environment 'Microsoft.App/managedEnvironments@2025-07-01' existing = { name: containerEnvironmentName }
resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = { name: acrName }
resource appIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: appIdentityName
}
var commonEnvironment = [
  { name: 'PHOTO_OGIRI_DATABASE_URL', secretRef: 'database-url' }
  { name: 'PHOTO_OGIRI_STORAGE_BACKEND', value: 'azure' }
  { name: 'PHOTO_OGIRI_AZURE_STORAGE_ACCOUNT_URL', value: storage.properties.primaryEndpoints.blob }
  { name: 'PHOTO_OGIRI_AZURE_QUEUE_ACCOUNT_URL', value: storage.properties.primaryEndpoints.queue }
  { name: 'PHOTO_OGIRI_SCORING_BACKEND', value: 'queue' }
  { name: 'PHOTO_OGIRI_MAX_PLAYERS', value: '100' }
  { name: 'AZURE_CLIENT_ID', value: appIdentityClientId }
]

resource api 'Microsoft.App/containerApps@2025-07-01' = {
  name: '${take(acrName, 24)}-api'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${appIdentity.id}': {} }
  }
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
      registries: [{ server: registry.properties.loginServer, identity: appIdentity.id }]
      secrets: [{ name: 'database-url', value: databaseUrl }]
    }
    template: {
      containers: [{
        name: 'api'
        image: apiImage
        env: commonEnvironment
        resources: { cpu: json('1.0'), memory: '2Gi' }
        probes: [
          {
            type: 'Startup'
            httpGet: { path: '/api/health', port: 8000 }
            initialDelaySeconds: 5
            periodSeconds: 5
            failureThreshold: 24
          }
          {
            type: 'Readiness'
            httpGet: { path: '/api/health', port: 8000 }
            periodSeconds: 10
          }
          {
            type: 'Liveness'
            httpGet: { path: '/api/health', port: 8000 }
            initialDelaySeconds: 20
            periodSeconds: 20
          }
        ]
      }]
      scale: {
        minReplicas: 1
        maxReplicas: 4
        rules: [{ name: 'http', http: { metadata: { concurrentRequests: '30' } } }]
      }
    }
  }
}

resource worker 'Microsoft.App/containerApps@2025-07-01' = {
  name: '${take(acrName, 21)}-worker'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${appIdentity.id}': {} }
  }
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      registries: [{ server: registry.properties.loginServer, identity: appIdentity.id }]
      secrets: [{ name: 'database-url', value: databaseUrl }]
    }
    template: {
      containers: [{
        name: 'worker'
        image: workerImage
        env: commonEnvironment
        resources: { cpu: json('2.0'), memory: '4Gi' }
      }]
      scale: { minReplicas: 1, maxReplicas: 1 }
    }
  }
}

output applicationUrl string = 'https://${api.properties.configuration.ingress.fqdn}'
output apiName string = api.name
output workerName string = worker.name