"""Adaptateurs d'import de formats externes (ADR 011).

Chaque format vit dans son propre module, seul autorisé à importer la
bibliothèque tierce correspondante. Le domaine métier (app.ifc_import,
app.assets, app.spatial...) ne dépend jamais que des structures simples
renvoyées ici, jamais de la bibliothèque elle-même : remplacer un parseur
ne doit jamais toucher au modèle métier.
"""
