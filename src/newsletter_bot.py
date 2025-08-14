"""Command line interface for newsletter bot."""

import asyncio
import logging

import aiohttp
import click

# Import heavy dependencies lazily within command functions to avoid
# requiring optional packages (like pydantic and aiohttp) just to load
# the CLI module.  This keeps ``cli`` importable in environments where
# the full runtime dependencies aren't installed – for example during
# basic tests that only check command registration.

logger = logging.getLogger(__name__)


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug mode")
@click.pass_context
def cli(ctx: click.Context, debug: bool) -> None:
    """Newsletter automation bot CLI.

    Aggregates content from multiple sources, processes with AI,
    and generates publication-ready newsletter drafts.
    """
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
    # Set up logging before any other logging calls
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=log_level, force=True)
    logger.debug("Debug mode enabled")


@cli.command()
@click.option("--dry-run", is_flag=True, help="Generate newsletter without publishing")
@click.option(
    "--from-draft",
    type=click.Path(exists=True),
    help="Publish from existing draft file",
)
@click.pass_context
def generate(ctx: click.Context, dry_run: bool, from_draft: str) -> None:
    """Generate a new newsletter from available content sources or publish from draft."""

    async def _generate():
        try:
            # Lazy imports to avoid importing heavy dependencies when the
            # CLI module is merely imported (e.g. during tests).
            from src.core.newsletter import NewsletterGenerator
            from src.models.settings import Settings

            settings = Settings(debug=ctx.obj.get("debug", False))
            logger.info("Starting newsletter generation...")

            # Validate that we have the required API keys
            # For dry-run mode with RSS feeds, we can be more lenient
            if dry_run and settings.rss_feeds:
                logger.info(
                    "🧪 Dry-run mode with RSS feeds - relaxed API key validation"
                )
                missing_critical = []
                # Only OpenRouter is truly required for content processing
                if not settings.openrouter_api_key:
                    missing_critical.append("OpenRouter")

                if missing_critical:
                    logger.warning(
                        f"⚠️  Missing API keys: {', '.join(missing_critical)}"
                    )
                    logger.info(
                        "Continuing with available sources (content may not be AI-processed)"
                    )
            else:
                required_keys = [
                    ("readwise_api_key", "Readwise"),
                    ("buttondown_api_key", "Buttondown"),
                    ("openrouter_api_key", "OpenRouter"),
                ]

                missing_keys = []
                for key, service in required_keys:
                    if not getattr(settings, key):
                        missing_keys.append(service)

                if missing_keys:
                    logger.error(
                        f"Missing required API keys for: {', '.join(missing_keys)}"
                    )
                    logger.error(
                        "Please configure secrets in Infisical or environment variables"
                    )
                    return

            logger.info("✅ Configuration validated")

            if from_draft:
                logger.info(f"📄 PUBLISHING FROM DRAFT: {from_draft}")
                # Read the draft content
                from pathlib import Path

                draft_content = Path(from_draft).read_text(encoding="utf-8")

                # Initialize newsletter generator for publishing only
                generator = NewsletterGenerator(settings)

                # Create a newsletter draft object from the file
                from src.models.content import NewsletterDraft

                newsletter = NewsletterDraft(
                    title="Newsletter from Draft",
                    content=draft_content,
                    items=[],  # Items already processed in the draft
                    metadata={"source": "draft_file", "draft_path": from_draft},
                )

                # Publish directly (skip generation, go straight to publishing)
                if not dry_run:
                    logger.info("🚀 Publishing newsletter from draft...")
                    await generator._publish_newsletter(newsletter)
                    logger.info("✅ Newsletter published successfully from draft")
                else:
                    logger.info(
                        "🔍 DRY RUN MODE - Draft content loaded but not published"
                    )

            else:
                if dry_run:
                    logger.info(
                        "🔍 DRY RUN MODE - No actual newsletter will be published"
                    )

                # Initialize newsletter generator
                generator = NewsletterGenerator(settings)

                # Test connections first
                logger.info("🔍 Testing service connections...")
                connections = await generator.test_connections()

                failed_connections = [
                    service
                    for service, status in connections.items()
                    if not status and service != "rss_feeds"
                ]

                if failed_connections:
                    logger.warning(
                        f"⚠️  Some services are unavailable: "
                        f"{', '.join(failed_connections)}"
                    )
                    logger.info("Continuing with available sources...")

                # Generate newsletter
                newsletter = await generator.generate_newsletter(dry_run=dry_run)

            # Display results
            logger.info(f"📧 Generated newsletter: '{newsletter.title}'")
            logger.info(f"📊 Total content items: {len(newsletter.items)}")

            if newsletter.metadata:
                if newsletter.metadata.get("readwise_items"):
                    logger.info(
                        f"   - Readwise highlights: "
                        f"{newsletter.metadata['readwise_items']}"
                    )
                if newsletter.metadata.get("rss_items"):
                    logger.info(
                        f"   - RSS articles: {newsletter.metadata['rss_items']}"
                    )

                # Show editorial workflow stats
                if newsletter.metadata.get("editorial_stats"):
                    stats = newsletter.metadata["editorial_stats"]
                    articles_processed = stats.get("articles_processed", 0)

                    if articles_processed > 0:
                        logger.info("🎭 Editorial Workflow Results:")
                        logger.info(f"   - Articles processed: {articles_processed}")
                        logger.info(
                            f"   - Articles revised: {stats.get('articles_revised', 0)}"
                        )
                        logger.info(
                            f"   - Average editor score: {stats.get('avg_editor_score', 'N/A')}/10"
                        )
                        if stats.get("newsletter_editor_score"):
                            logger.info(
                                f"   - Newsletter editor score: {stats['newsletter_editor_score']}/10"
                            )
                        if stats.get("total_revisions"):
                            logger.info(
                                f"   - Total revisions made: {stats['total_revisions']}"
                            )

                        # Show any editorial feedback summaries
                        if stats.get("common_feedback_themes"):
                            logger.info(
                                f"   - Common editor feedback: {', '.join(stats['common_feedback_themes'])}"
                            )
                    else:
                        logger.info(
                            "🎭 Editorial Workflow: ⚠️  Skipped (OpenRouter API key not configured)"
                        )
                        logger.info(
                            "   - Set OPENROUTER_API_KEY to enable AI-powered editorial review and revision"
                        )
                        logger.info(
                            "   - Content processed using basic formatting without AI enhancement"
                        )

                if newsletter.metadata.get("processing_time"):
                    logger.info(
                        f"   - Processing time: {newsletter.metadata['processing_time']:.1f}s"
                    )

            # Show preview of content
            content_preview = (
                newsletter.content[:200] + "..."
                if len(newsletter.content) > 200
                else newsletter.content
            )
            logger.info(f"📝 Content preview: {content_preview}")

            if not dry_run:
                logger.info("✅ Newsletter generation completed successfully!")
            else:
                logger.info("✅ Dry run completed successfully!")

        except (ImportError, ModuleNotFoundError) as e:
            logger.error(f"❌ Missing required dependencies: {e}")
            if ctx.obj.get("debug"):
                raise
            import sys

            sys.exit(1)
        except (KeyError, AttributeError, ValueError, TypeError) as e:
            logger.error(f"❌ Configuration or data error: {e}")
            if ctx.obj.get("debug"):
                raise
            import sys

            sys.exit(1)
        except (FileNotFoundError, PermissionError) as e:
            logger.error(f"❌ File system error: {e}")
            if ctx.obj.get("debug"):
                raise
            import sys

            sys.exit(1)
        except Exception as e:
            logger.error(f"❌ Unexpected newsletter generation error: {e}")
            if ctx.obj.get("debug"):
                raise
            # Exit with non-zero code to indicate failure
            import sys

            sys.exit(1)

    asyncio.run(_generate())


@cli.command()
def health() -> None:
    """Check system health and configuration."""
    try:
        # Import Settings lazily to avoid requiring optional dependencies
        # when merely importing the CLI module.
        from src.core.newsletter import NewsletterGenerator
        from src.models.settings import Settings

        settings = Settings()
        logger.info("🔍 Checking system health...")

        # Check configuration
        logger.info("📋 Configuration:")
        logger.info(f"   - Debug mode: {settings.debug}")
        logger.info(f"   - Log level: {settings.log_level}")
        logger.info(f"   - Infisical enabled: {settings.use_infisical}")

        # Check API key availability (without showing values)
        api_keys = {
            "Readwise": bool(settings.readwise_api_key),
            "Glasp": bool(settings.glasp_api_key),
            "Buttondown": bool(settings.buttondown_api_key),
            "OpenRouter": bool(settings.openrouter_api_key),
            "Unsplash": bool(settings.unsplash_api_key),
        }

        # Test actual connections
        try:
            generator = NewsletterGenerator(settings)
            logger.info("🔍 Testing service connections...")
            connections = asyncio.run(generator.test_connections())

            logger.info("🌐 Connection status:")
            for service, status in connections.items():
                if service == "rss_feeds":
                    for feed_url, feed_status in status.items():
                        status_icon = "✅" if feed_status else "❌"
                        logger.info(
                            f"   - RSS Feed ({feed_url[:50]}...): {status_icon}"
                        )
                else:
                    status_icon = "✅" if status else "❌"
                    logger.info(f"   - {service.title()}: {status_icon}")

        except (ImportError, ModuleNotFoundError) as e:
            logger.warning(f"Missing dependencies for connection testing: {e}")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.warning(f"Network error during connection testing: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error during connection testing: {e}")

        logger.info("🔑 API Keys status:")
        for service, available in api_keys.items():
            status = "✅" if available else "❌"
            logger.info(f"   - {service}: {status}")

        # Check RSS feeds
        rss_count = len(settings.rss_feeds.split(",")) if settings.rss_feeds else 0
        logger.info(f"📡 RSS feeds: {rss_count} configured")

        # Overall health
        critical_keys = ["Readwise", "Buttondown", "OpenRouter"]
        critical_missing = [k for k in critical_keys if not api_keys[k]]

        if critical_missing:
            logger.warning(
                f"⚠️  Missing critical API keys: {', '.join(critical_missing)}"
            )
            logger.info("🔧 System partially functional - some features may not work")
        else:
            logger.info("✅ System healthy - all critical components configured")

    except (ImportError, ModuleNotFoundError) as e:
        logger.error(f"❌ Missing required dependencies for health check: {e}")
        raise
    except (KeyError, AttributeError, ValueError) as e:
        logger.error(f"❌ Configuration error during health check: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error during health check: {e}")
        raise


@cli.command()
def config() -> None:
    """Display current configuration (without sensitive values)."""
    try:
        from src.models.settings import Settings

        settings = Settings()

        click.echo("\n📋 Newsletter Bot Configuration\n")
        click.echo(f"Debug Mode: {settings.debug}")
        click.echo(f"Log Level: {settings.log_level}")
        click.echo(f"Infisical Enabled: {settings.use_infisical}")

        click.echo("\n🔑 API Keys:")
        keys_status = {
            "Readwise": "✅ Configured" if settings.readwise_api_key else "❌ Missing",
            "Glasp": "✅ Configured" if settings.glasp_api_key else "❌ Missing",
            "Buttondown": (
                "✅ Configured" if settings.buttondown_api_key else "❌ Missing"
            ),
            "OpenRouter": (
                "✅ Configured" if settings.openrouter_api_key else "❌ Missing"
            ),
            "Unsplash": "✅ Configured" if settings.unsplash_api_key else "❌ Missing",
        }

        for service, status in keys_status.items():
            click.echo(f"  {service}: {status}")

        rss_count = len(settings.rss_feeds.split(",")) if settings.rss_feeds else 0
        click.echo("\n📡 Content Sources:")
        click.echo(f"  RSS Feeds: {rss_count} configured")
        click.echo(f"  Readwise Filter Tag: '{settings.readwise_filter_tag}'")

        if settings.rss_feeds and rss_count > 0:
            click.echo("\n📋 RSS Feed URLs:")
            for i, url in enumerate(settings.rss_feeds.split(","), 1):
                click.echo(f"  {i}. {url.strip()}")

    except (ImportError, ModuleNotFoundError) as e:
        click.echo(f"❌ Missing required dependencies for configuration: {e}")
        raise
    except (KeyError, AttributeError, ValueError, TypeError) as e:
        click.echo(f"❌ Configuration data error: {e}")
        raise
    except Exception as e:
        click.echo(f"❌ Unexpected error loading configuration: {e}")
        raise


@cli.command()
@click.option("--voice", default=None, help="Specific voice to show info for")
def voices(voice: str) -> None:
    """List available voices and their configurations."""
    try:
        from src.core.voice_manager import VoiceManager
        
        voice_manager = VoiceManager()
        available_voices = voice_manager.list_available_voices()
        
        if voice:
            # Show specific voice info
            voice_info = next((v for v in available_voices if v["name"] == voice), None)
            if not voice_info:
                click.echo(f"❌ Voice '{voice}' not found")
                return
            
            click.echo(f"\n🎤 Voice: {voice_info['name']}")
            click.echo(f"Description: {voice_info['description']}")
            click.echo(f"Languages: {', '.join(voice_info['languages'])}")
            click.echo(f"Themes: {', '.join(voice_info['themes'])}")
            click.echo(f"Default options: {voice_info['default_options']}")
        else:
            # List all voices
            click.echo("\n🎤 Available Voices:\n")
            for voice_info in available_voices:
                status = "✅ Active" if voice_info["name"] == "saint" else "📋 Available"
                click.echo(f"  {voice_info['name']}: {status}")
                click.echo(f"    {voice_info['description']}")
                click.echo(f"    Languages: {', '.join(voice_info['languages'])}")
                click.echo()
            
            click.echo("💡 Use --voice <name> to see detailed configuration")
            click.echo("💡 Set DEFAULT_VOICE environment variable to change default")
            
    except Exception as e:
        click.echo(f"❌ Error loading voices: {e}")
        raise


@cli.command()
@click.argument("voice_file", type=click.Path(exists=True))
def add_voice(voice_file: str) -> None:
    """Add a custom voice from a Python file."""
    try:
        from src.core.voice_manager import VoiceManager
        
        voice_manager = VoiceManager()
        voice_manager.add_custom_voice(voice_file)
        
        click.echo(f"✅ Successfully added custom voice from: {voice_file}")
        click.echo("💡 Use 'newsletter-bot voices' to see all available voices")
        
    except Exception as e:
        click.echo(f"❌ Failed to add voice: {e}")
        raise


if __name__ == "__main__":
    cli()
