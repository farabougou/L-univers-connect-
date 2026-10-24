"""Adaptateurs réglementaires : au-dessus des moteurs internes (énergie,
fluides frigorigènes…), jamais à l'intérieur. Voir docs/regulatory/ pour les
références officielles et la politique `DEFERRED_EXTERNAL_INTEGRATION` /
`TO_FINALIZE` (directive de Mohamed, 02/10/2026) : une intégration externe
indisponible aujourd'hui (compte, identifiants API, spécification) ne bloque
jamais le modèle de données, le workflow ni l'interface — seul l'appel
externe réel est différé, jamais simulé.
"""
