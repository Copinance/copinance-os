# Governance

This document outlines the governance model for the Copinance OS project.

## Project Mission

Copinance OS aims to democratize financial research by providing an open-source, extensible framework that makes institutional-grade market research accessible to everyone, regardless of their financial resources or technical expertise.

See our [MANIFESTO.md](MANIFESTO.md) for the complete vision.

## Project Status

**Current Phase**: Early Development (v0.1.x - Alpha)

As an early-stage project, we are currently establishing our governance structure. This document will evolve as the community grows.

## Core Principles

1. **Openness**: All discussions, decisions, and development happen in public
2. **Meritocracy**: Contributions and commitment earn influence
3. **Transparency**: Decision-making processes are documented and visible
4. **Inclusivity**: Everyone is welcome to contribute, regardless of background
5. **Quality**: We maintain high standards for code, documentation, and community interactions
6. **Mission-Driven**: All decisions align with democratizing financial research

## Roles and Responsibilities

### Users

Anyone who uses Copinance OS.

**Rights**:
- Use the software under the Apache 2.0 License
- Report bugs and request features
- Participate in discussions

**How to Become**: Use the software!

### Contributors

Anyone who contributes to the project through code, documentation, design, or community support.

**Rights**:
- All User rights
- Recognition in contributors list
- Vote on non-binding polls
- Participate in technical discussions

**Responsibilities**:
- Follow the [Contributing Guidelines](CONTRIBUTING.md)
- Be respectful and constructive

**How to Become**: Submit a merged pull request or make significant contributions to discussions, documentation, or community support.

### Committers

Regular contributors who have shown commitment to the project and have been granted write access to the repository.

**Rights**:
- All Contributor rights
- Merge pull requests
- Triage and label issues
- Participate in committer discussions
- Vote on technical decisions

**Responsibilities**:
- Review pull requests thoughtfully and promptly
- Maintain code quality standards
- Help onboard new contributors
- Follow and enforce project guidelines
- Act as shepherds for specific areas of the codebase
- Participate actively in project discussions

**How to Become**:
- Minimum 5 merged pull requests of substance
- Demonstrated understanding of the architecture
- Active participation for 2+ months
- Nominated by existing committer
- Approved by majority of maintainers

### Maintainers

Core team members who have significant decision-making authority and are responsible for the project's direction.

**Rights**:
- All Committer rights
- Make architectural decisions
- Create and manage releases
- Modify governance policies
- Add/remove committers
- Access to project resources (domain, social accounts, etc.)

**Responsibilities**:
- Guide project direction and roadmap
- Ensure project health and sustainability
- Make final decisions on contentious issues
- Manage security issues and disclosures
- Foster a healthy community culture
- Regularly review governance and adapt as needed

**Current Maintainers**:
- Founding team (to be listed)

**How to Become**:
- Significant sustained contributions over 6+ months
- Demonstrated leadership in the community
- Deep understanding of project architecture and vision
- Nominated by existing maintainer
- Unanimous approval by current maintainers

### Project Lead

The project lead has final authority on all decisions and is responsible for the overall health of the project.

**Current Lead**: *To be designated*

**Responsibilities**:
- Break ties in maintainer decisions
- Handle Code of Conduct violations
- Represent the project publicly
- Ensure governance is followed
- Plan for succession

## Decision Making

### Consensus Building

We prefer **lazy consensus** for most decisions:

1. **Proposal**: Someone proposes an idea (issue, discussion, or PR)
2. **Discussion**: Community discusses the proposal
3. **Refinement**: Proposal is refined based on feedback
4. **Approval**: If no objections after 72 hours, proposal is accepted

**Objections must be constructive** and include:
- Clear explanation of concerns
- Suggested alternatives or modifications
- Alignment with project mission

### Voting

When consensus cannot be reached, we use voting:

#### Types of Votes

**Technical Decisions** (architecture, major features):
- **Who votes**: Committers and Maintainers
- **Threshold**: 2/3 majority
- **Example**: "Should we adopt GraphQL for the API?"

**Governance Decisions** (roles, policies):
- **Who votes**: Maintainers only
- **Threshold**: Simple majority (51%)
- **Example**: "Should we add a new committer?"

**Critical Decisions** (license change, fork, major pivots):
- **Who votes**: Maintainers only
- **Threshold**: Unanimous (100%)
- **Example**: "Should we change the license?"

#### Voting Process

1. **Proposal**: Clear written proposal with rationale
2. **Discussion Period**: Minimum 7 days for discussion
3. **Call for Vote**: Explicit call for vote with clear options
4. **Voting Period**: 7 days minimum
5. **Result**: Announced publicly with vote tally

### Fast-Track Decisions

Some decisions can be made quickly:

- **Bug fixes**: Can be merged immediately
- **Documentation fixes**: Can be merged immediately
- **Dependencies updates**: Can be merged after CI passes
- **Minor refactoring**: Can be merged with one approving review

## Areas of Decision Making

### Architecture Decisions

**Who Decides**: Maintainers with input from committers

**Process**:
1. Create an Architecture Decision Record (ADR) in `docs/adr/`
2. Discuss for minimum 7 days
3. Vote if no consensus

**Recent ADRs**: (To be populated)

### Roadmap and Priorities

**Who Decides**: Maintainers with community input

**Process**:
1. Community discussions on priorities
2. Maintainers synthesize into roadmap
3. Published quarterly in `ROADMAP.md`

### Release Management

**Who Decides**: Maintainers

**Process**:
- Follow [Semantic Versioning](https://semver.org/)
- Release notes required for all releases
- Security releases can skip normal discussion period

**Release Cadence**:
- **Major** (X.0.0): When breaking changes accumulate (no fixed schedule)
- **Minor** (0.X.0): Monthly or when significant features are ready
- **Patch** (0.0.X): As needed for bug fixes and security issues

### Code Review

**All code must be reviewed before merging**, except:
- Documentation typo fixes
- Emergency security patches (must be reviewed post-merge)

**Review Requirements**:
- **Normal PRs**: 1 approving review from committer/maintainer
- **Breaking changes**: 2 approving reviews, one from maintainer
- **Security fixes**: 1 review from maintainer
- **CI must pass**: All automated checks must be green

### Code of Conduct Enforcement

**Who Decides**: Maintainers

**Process**:
1. Report received (private or public)
2. Maintainers discuss privately
3. Decision made within 48 hours for urgent issues

## Communication Channels

### Public Channels

- **GitHub Issues**: Bug reports, feature requests, tasks
- **GitHub Discussions**: Questions, ideas, general discussion
- **GitHub Pull Requests**: Code review and technical discussion
- **Discord/Slack**: (To be set up) Real-time community chat

### Private Channels

- **Security Issues**: Via GitHub Security Advisories or security@copinance-os.org
- **Code of Conduct**: Via maintainers@copinance-os.org
- **Maintainer Discussions**: Private maintainer channel (for sensitive topics only)

**Default to Public**: Only use private channels for security issues, CoC violations, or personal matters.

## Conflict Resolution

When conflicts arise:

1. **Direct Communication**: Parties try to resolve directly
2. **Mediation**: Involve a neutral committer or maintainer
3. **Maintainer Decision**: Maintainers make final call if unresolved
4. **Project Lead**: Project lead makes final decision if maintainers are split

All parties must:
- Assume good intentions
- Focus on what's best for the project
- Respect the Code of Conduct
- Accept final decisions gracefully

## Changes to Governance

This governance document can be modified through:

1. **Proposal**: PR proposing changes to GOVERNANCE.md
2. **Discussion**: Minimum 14 days for community input
3. **Vote**: Unanimous approval by maintainers required
4. **Announcement**: Changes announced to community

## Attribution and Inspiration

This governance model is inspired by:
- [Apache Software Foundation Governance](https://www.apache.org/foundation/governance/)
- [Python's PEP Process](https://www.python.org/dev/peps/)
- [Contributor Covenant](https://www.contributor-covenant.org/)

## Appendix: Lifecycle of a Contribution

### Example: Feature Addition

```
1. Idea → GitHub Discussion
   └─ Community provides feedback

2. Proposal → GitHub Issue
   └─ Technical details fleshed out

3. Design → Architecture Decision (if significant)
   └─ Maintainers approve approach

4. Implementation → Pull Request
   └─ Code review by committers
   └─ CI checks pass

5. Merge → Main branch
   └─ Added to next release

6. Release → Published to PyPI
   └─ Announced in release notes
```

### Example: Bug Fix

```
1. Bug Report → GitHub Issue
   └─ Reproduce and confirm

2. Fix → Pull Request
   └─ Link to issue
   └─ Include test

3. Review → Committer approval
   └─ CI checks pass

4. Merge → Fast-track if urgent

5. Release → Patch version or next scheduled release
```

## Questions?

- **General questions**: Open a GitHub Discussion
- **Governance questions**: Create an issue with label `governance`
- **Private concerns**: Contact maintainers@copinance-os.org

---

**Last Updated**: December 20, 2025
**Version**: 1.0
**Status**: Living Document
