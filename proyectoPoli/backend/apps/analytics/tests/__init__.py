"""
Tests backend/API del módulo analytics (documento TC03 — casos TC01–TC07).

Casos incluidos al ejecutar ``python manage.py test apps.analytics``:
TC01.1, TC01.2, TC02.1, TC02.2, TC03.1, TC03.2,
TC04.1, TC04.2, TC04.3, TC05.1, TC05.2, TC05.3, TC07.1, TC07.3.

Excluidos (Playwright / manual): TC02.3, TC03.3, TC06.x, TC07.2.

El orden de ejecución sigue la numeración del documento (vía ``load_tests``).
"""
import unittest

# Módulos en orden TC01 → TC07 (sin TC06; TC07.2 excluido en el módulo habitos).
_ORDERED_TEST_MODULES = (
    "apps.analytics.tests.test_tendencias",
    "apps.analytics.tests.test_proyecciones",
    "apps.analytics.tests.test_detalle_visual_tendencia",
    "apps.analytics.tests.test_habitos_tendencias",
)


def load_tests(loader, standard_tests, pattern):
    """Carga los tests en orden numérico TC01.1 … TC07.3 (no alfabético por archivo)."""
    suite = unittest.TestSuite()
    for module_name in _ORDERED_TEST_MODULES:
        suite.addTests(loader.loadTestsFromName(module_name))
    return suite
