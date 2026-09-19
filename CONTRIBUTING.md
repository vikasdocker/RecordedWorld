# Contributing to Recorded World

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Getting Started

1. **Fork** the repository
2. **Clone** your fork: `git clone https://github.com/your-username/RecordedWorld.git`
3. **Create** a branch: `git checkout -b feature/my-feature`
4. **Make** your changes
5. **Test** your changes
6. **Commit** and **push**

## Development Setup

### Backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

### PC Client

```bash
cd pc-client
npm install
npm run dev
```

### UE5 Client

Requires Unreal Engine 5.8 installed via Epic Games Launcher.

### Mobile App

```bash
cd mobile-app
npm install
npx expo start
```

## Code Style

### Python (Backend)
- Follow PEP 8
- Use type hints
- Docstrings for public functions
- Maximum line length: 100 characters

### TypeScript (PC Client / Mobile)
- Use strict TypeScript
- Prefer `const` over `let`
- Use async/await over raw promises
- Follow ESLint rules

### C++ (UE5 Client)
- Use UE5 coding standards
- Prefix UPROPERTY/UFUNCTION with appropriate specifiers
- Use `TObjectPtr` for UPROPERTY object pointers
- Use `FLinearColor` for vertex colors

## Testing

### Backend Tests
```bash
cd backend
pytest tests/ -v
```

### PC Client Tests
```bash
cd pc-client
npx vitest run
```

### Mobile App Tests
```bash
cd mobile-app
npx vitest run
```

## Pull Request Guidelines

1. **Description**: Clear description of what the PR does
2. **Tests**: Add tests for new functionality
3. **Documentation**: Update docs if adding new features
4. **No secrets**: Never commit API keys, passwords, or tokens
5. **Single responsibility**: One PR per feature/fix

## Reporting Issues

Use GitHub Issues with:
- Clear title and description
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, browser, UE version)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
