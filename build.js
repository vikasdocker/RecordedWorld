const { execSync } = require('child_process');
const path = require('path');

console.log('Recording World - Build Script');
console.log('=============================\n');

const root = path.resolve(__dirname);
const steps = [
  {
    name: 'Backend',
    dir: path.join(root, 'backend'),
    commands: [
      'pip install -r requirements.txt',
    ],
  },
  {
    name: 'PC Client',
    dir: path.join(root, 'pc-client'),
    commands: [
      'npm install',
    ],
  },
  {
    name: 'Mobile App',
    dir: path.join(root, 'mobile-app'),
    commands: [
      'npm install',
    ],
  },
];

for (const step of steps) {
  console.log(`\nBuilding ${step.name}...`);
  console.log(`  Directory: ${step.dir}`);
  
  for (const cmd of step.commands) {
    console.log(`  Running: ${cmd}`);
    try {
      execSync(cmd, { 
        cwd: step.dir, 
        stdio: 'inherit',
        shell: true 
      });
      console.log(`  ✓ ${step.name} complete`);
    } catch (e) {
      console.error(`  ✗ Failed: ${cmd}`);
      console.error(e.message);
    }
  }
}

console.log('\n=============================');
console.log('Build complete!');
console.log('\nTo start the backend:');
console.log('  cd backend && python -m uvicorn app.main:app --reload');
console.log('\nTo start the PC client:');
console.log('  cd pc-client && npm run dev');
