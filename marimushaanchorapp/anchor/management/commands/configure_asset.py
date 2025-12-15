"""Management command to configure asset distribution_seed."""
from django.core.management.base import BaseCommand
from stellar_sdk import Keypair
from polaris.models import Asset
from django.conf import settings


class Command(BaseCommand):
    help = 'Configure distribution_seed for an asset'

    def add_arguments(self, parser):
        parser.add_argument(
            '--code',
            type=str,
            required=True,
            help='Asset code (e.g., TALE)',
        )
        parser.add_argument(
            '--seed',
            type=str,
            help='Stellar secret seed/key. If not provided, will use STELLAR_SECRET_KEY from settings or generate a new one.',
        )
        parser.add_argument(
            '--generate',
            action='store_true',
            help='Generate a new keypair for this asset',
        )

    def handle(self, *args, **options):
        asset_code = options['code']
        seed = options.get('seed')
        generate = options.get('generate', False)

        try:
            asset = Asset.objects.get(code=asset_code)
        except Asset.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Asset with code "{asset_code}" not found in database.')
            )
            self.stdout.write('Available assets:')
            for a in Asset.objects.all():
                self.stdout.write(f'  - {a.code} (issuer: {a.issuer})')
            return

        # Determine which seed to use
        if generate:
            new_keypair = Keypair.random()
            seed = new_keypair.secret
            self.stdout.write(
                self.style.WARNING(
                    f'Generated new keypair:\n'
                    f'  Secret: {seed}\n'
                    f'  Public: {new_keypair.public_key}\n'
                    f'  ⚠️  SAVE THIS SECRET KEY SECURELY!'
                )
            )
        elif seed:
            # Validate the seed
            try:
                keypair = Keypair.from_secret(seed)
                self.stdout.write(f'Using provided seed. Public key: {keypair.public_key}')
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Invalid secret seed: {e}')
                )
                return
        else:
            # Use STELLAR_SECRET_KEY from settings
            seed = getattr(settings, 'STELLAR_SECRET_KEY', None)
            if not seed:
                self.stdout.write(
                    self.style.ERROR(
                        'No seed provided and STELLAR_SECRET_KEY not found in settings.\n'
                        'Please provide --seed or --generate option.'
                    )
                )
                return
            try:
                keypair = Keypair.from_secret(seed)
                self.stdout.write(
                    f'Using STELLAR_SECRET_KEY from settings. Public key: {keypair.public_key}'
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Invalid STELLAR_SECRET_KEY in settings: {e}')
                )
                return

        # Update the asset
        asset.distribution_seed = seed
        asset.save()

        # Verify
        distribution_account = asset.distribution_account
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Successfully configured distribution_seed for asset {asset_code}!\n'
                f'  Distribution account: {distribution_account}\n'
                f'  Issuer: {asset.issuer}'
            )
        )

