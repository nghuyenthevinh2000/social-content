"""Default CLI entrypoint for tools.loop.viral_analyzer (routes to profile_research)."""

from tools.loop.viral_analyzer.profile_research.pipeline import main

if __name__ == "__main__":
    main()
