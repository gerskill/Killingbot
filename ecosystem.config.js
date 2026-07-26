module.exports = {
  apps: [
    {
      name: 'killingbot-webhook',
      script: 'webhook_server.py',
      interpreter: 'python3',
      cwd: '/Users/leclercq/Documents/Claude/Projects/Killingbot',
      watch: false,
      autorestart: true,
      max_restarts: 10,
      env: {
        PORT: 5001
      }
    }
  ]
};
