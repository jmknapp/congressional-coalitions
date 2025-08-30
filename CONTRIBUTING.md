# Contributing to Congressional Coalitions

Thank you for your interest in contributing to the Congressional Coalitions project! This document provides guidelines for contributing to the codebase.

## Getting Started

1. Fork the repository
2. Clone your fork locally
3. Create a virtual environment: `python -m venv venv`
4. Activate the virtual environment: `source venv/bin/activate` (Linux/Mac) or `venv\Scripts\activate` (Windows)
5. Install dependencies: `pip install -r requirements.txt`
6. Create a new branch for your feature: `git checkout -b feature/your-feature-name`

## Development Guidelines

### Code Style
- Follow PEP 8 style guidelines
- Use meaningful variable and function names
- Add docstrings to functions and classes
- Keep functions focused and concise

### Testing
- Write tests for new functionality
- Ensure all tests pass before submitting a PR
- Run tests with: `pytest`

### Database Changes
- If you modify the database schema, update the setup script
- Document any new tables or columns
- Consider backward compatibility

### Data Sources
- When adding new data sources, document the source and format
- Include sample data or examples where possible
- Update the README with new data sources

## Pull Request Process

1. Ensure your code follows the style guidelines
2. Add tests for new functionality
3. Update documentation as needed
4. Submit a pull request with a clear description
5. Wait for review and address any feedback

## Areas for Contribution

### High Priority
- Database schema improvements
- Data loading and ETL processes
- Coalition detection algorithms
- Outlier detection models

### Medium Priority
- Web dashboard improvements
- API endpoints
- Documentation
- Performance optimizations

### Low Priority
- UI/UX improvements
- Additional data sources
- Advanced analytics features

## Questions or Issues?

If you have questions or encounter issues:
1. Check the existing issues
2. Create a new issue with a clear description
3. Include error messages and steps to reproduce

## License

By contributing to this project, you agree that your contributions will be licensed under the MIT License.
