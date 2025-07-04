# Contributing to Music Automation Toolkit

Thank you for your interest in contributing to the Music Automation Toolkit! This document provides guidelines and information for contributors.

## 🚀 Getting Started

### Prerequisites

- Python 3.11 or higher
- SoX and FLAC tools installed on your system
- Git for version control

### Setting Up Development Environment

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/yourusername/MusicAutomation.git
   cd MusicAutomation
   ```

3. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # Development dependencies
   ```

5. Install system dependencies:
   ```bash
   # macOS
   brew install sox flac
   
   # Ubuntu/Debian
   sudo apt-get install sox flac
   
   # Windows
   # Download and install SoX and FLAC manually
   ```

## 📝 Development Guidelines

### Code Style

- Follow PEP 8 guidelines
- Use type hints where possible
- Add docstrings to functions and classes
- Keep functions focused and single-purpose
- Use meaningful variable and function names

### Commit Messages

Follow conventional commits format:
- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation changes
- `style:` for formatting changes
- `refactor:` for code refactoring
- `test:` for adding tests
- `chore:` for maintenance tasks

Example:
```
feat: add support for XLSX playlist format
fix: resolve M3U parsing issue with file paths
docs: update README with new features
```

### Branch Naming

- `feature/description` for new features
- `bugfix/description` for bug fixes
- `hotfix/description` for critical fixes
- `docs/description` for documentation updates

## 🧪 Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/

# Run specific test file
pytest tests/test_playlist_matching.py
```

### Writing Tests

- Write unit tests for new functions
- Include integration tests for major features
- Test edge cases and error conditions
- Use descriptive test names

Example test structure:
```python
def test_playlist_parsing_m3u_with_file_paths():
    """Test M3U parsing when file contains full file paths."""
    # Arrange
    test_data = "..."
    
    # Act
    result = parse_m3u_file(test_data)
    
    # Assert
    assert len(result) == expected_count
    assert result[0]['artist'] == 'Expected Artist'
```

## 🐛 Reporting Issues

### Bug Reports

When reporting bugs, please include:
- Operating system and version
- Python version
- Steps to reproduce the issue
- Expected vs actual behavior
- Error messages or logs
- Sample files (if applicable)

### Feature Requests

For feature requests, please provide:
- Clear description of the proposed feature
- Use cases and motivation
- Possible implementation approaches
- Any relevant examples or mockups

## 🔄 Pull Request Process

1. **Create a branch** from `main` for your changes
2. **Write tests** for your changes
3. **Update documentation** if needed
4. **Ensure all tests pass** locally
5. **Submit a pull request** with:
   - Clear title and description
   - Link to related issues
   - Screenshots (if UI changes)
   - Testing instructions

### Pull Request Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Tests pass locally
- [ ] Added new tests for changes
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes (or properly documented)
```

## 📚 Documentation

- Update README.md for significant changes
- Add docstrings to new functions/classes
- Update CLI documentation for command changes
- Include examples for new features

## 🎯 Areas for Contribution

### High Priority
- Performance optimizations
- Additional playlist formats
- Error handling improvements
- Cross-platform compatibility

### Medium Priority
- UI/UX enhancements
- Additional export formats
- Integration with music services
- Configuration management

### Low Priority
- Code organization
- Documentation improvements
- Test coverage
- Example scripts

## 💬 Getting Help

- **GitHub Issues**: For bug reports and feature requests
- **Discussions**: For questions and general discussion
- **Email**: [your-email@example.com] for private inquiries

## 📄 License

By contributing to this project, you agree that your contributions will be licensed under the MIT License.

Thank you for contributing! 🎵
