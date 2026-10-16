"""app/storage.py : les fonctions `*_key_belongs_to` sont la seule barrière
entre une clé d'objet fournie par le client (POST .../documents,
.../floor-plans, .../ifc-imports) et une URL de téléchargement présignée
pour cette clé — voir app/routers/documents.py, floor_plans.py,
ifc_import.py. Audit de sécurité du 16/10/2026 (pistes Siemens
SSA-832641, CWE-35 "Path Traversal") : ces fonctions n'avaient jamais été
testées directement, seulement couvertes indirectement par un test
« clé d'un autre équipement » côté API. Ce fichier teste explicitement
les chemins hors dossier autorisé et les clés d'un autre tenant.
"""

import uuid

from app.storage import (
    build_document_object_key,
    build_floor_plan_object_key,
    build_ifc_import_object_key,
    build_object_key,
    document_key_belongs_to,
    floor_plan_key_belongs_to,
    ifc_import_key_belongs_to,
    key_belongs_to,
)

# Les quatre paires (construire, vérifier) partagent exactement le même
# contrat — un dossier `{tenant}/{...}/{resource}/` sans sous-dossier —
# donc les mêmes cas adverses, paramétrés une fois par fonction plutôt que
# dupliqués quatre fois (règle des trois : au-delà de deux occurrences,
# factoriser).
_CASES = (
    (build_object_key, key_belongs_to, "intervention_id"),
    (build_floor_plan_object_key, floor_plan_key_belongs_to, "space_id"),
    (build_ifc_import_object_key, ifc_import_key_belongs_to, "site_id"),
    (build_document_object_key, document_key_belongs_to, "functional_location_id"),
)


def test_une_cle_legitime_est_acceptee():
    for build, belongs_to, resource_kwarg in _CASES:
        tenant_id = uuid.uuid4()
        resource_id = uuid.uuid4()
        key = build(tenant_id=tenant_id, filename="x.pdf", **{resource_kwarg: resource_id})
        assert belongs_to(key, tenant_id=tenant_id, **{resource_kwarg: resource_id})


def test_une_cle_d_un_autre_tenant_est_refusee():
    """Le cas central de l'audit : connaître (ou deviner) la clé d'un
    fichier d'un autre client ne doit jamais suffire à se faire livrer une
    URL de téléchargement pour ce fichier."""
    for build, belongs_to, resource_kwarg in _CASES:
        victim_tenant_id = uuid.uuid4()
        attacker_tenant_id = uuid.uuid4()
        resource_id = uuid.uuid4()
        victim_key = build(
            tenant_id=victim_tenant_id, filename="secret.pdf", **{resource_kwarg: resource_id}
        )
        assert not belongs_to(
            victim_key, tenant_id=attacker_tenant_id, **{resource_kwarg: resource_id}
        )


def test_une_cle_d_une_autre_ressource_du_meme_tenant_est_refusee():
    for build, belongs_to, resource_kwarg in _CASES:
        tenant_id = uuid.uuid4()
        own_resource_id = uuid.uuid4()
        foreign_resource_id = uuid.uuid4()
        foreign_key = build(
            tenant_id=tenant_id, filename="x.pdf", **{resource_kwarg: foreign_resource_id}
        )
        assert not belongs_to(foreign_key, tenant_id=tenant_id, **{resource_kwarg: own_resource_id})


def test_une_sequence_de_traversee_imbriquee_est_refusee():
    """Motif cité par l'avis Siemens SSA-832641 (CWE-35, « .../...//ETC ») :
    une séquence de traversée qui survivrait à un filtre naïf ne retirant
    qu'une seule occurrence de "../". Ici, aucun filtre de nettoyage
    n'existe : la présence du moindre "/" dans la partie nom suffit à
    refuser (voir app/storage.py), donc ce motif est bloqué par
    construction plutôt que par une liste noire — qu'il soit imbriqué
    ("..../") ou non."""
    for build, belongs_to, resource_kwarg in _CASES:
        tenant_id = uuid.uuid4()
        resource_id = uuid.uuid4()
        other_tenant_id = uuid.uuid4()
        other_resource_id = uuid.uuid4()
        prefix = build(
            tenant_id=tenant_id, filename="x.pdf", **{resource_kwarg: resource_id}
        ).rsplit("/", 1)[0]
        suffix = f"{other_tenant_id}/x/{other_resource_id}/secret.pdf"

        for traversal_segment in ("../../", "..../...//", "..%2f..%2f"):
            key = f"{prefix}/{traversal_segment}{suffix}"
            assert not belongs_to(key, tenant_id=tenant_id, **{resource_kwarg: resource_id})


def test_une_cle_egale_au_dossier_lui_meme_est_refusee():
    """Pas de nom de fichier du tout (clé = préfixe seul, avec ou sans la
    barre finale) : rien à télécharger, jamais acceptée comme une clé
    valide."""
    for build, belongs_to, resource_kwarg in _CASES:
        tenant_id = uuid.uuid4()
        resource_id = uuid.uuid4()
        prefix = build(
            tenant_id=tenant_id, filename="x.pdf", **{resource_kwarg: resource_id}
        ).rsplit("/", 1)[0]
        assert not belongs_to(prefix, tenant_id=tenant_id, **{resource_kwarg: resource_id})
        assert not belongs_to(prefix + "/", tenant_id=tenant_id, **{resource_kwarg: resource_id})


def test_un_nom_de_fichier_point_ou_point_point_est_refuse():
    for build, belongs_to, resource_kwarg in _CASES:
        tenant_id = uuid.uuid4()
        resource_id = uuid.uuid4()
        prefix = build(
            tenant_id=tenant_id, filename="x.pdf", **{resource_kwarg: resource_id}
        ).rsplit("/", 1)[0]
        assert not belongs_to(prefix + "/.", tenant_id=tenant_id, **{resource_kwarg: resource_id})
        assert not belongs_to(prefix + "/..", tenant_id=tenant_id, **{resource_kwarg: resource_id})


def test_le_nom_de_fichier_ne_peut_jamais_contenir_un_separateur():
    """`build_*` remplace déjà "/" par "_" dans le nom fourni — ce test
    vérifie la propriété elle-même, pas seulement l'implémentation
    actuelle : un futur appel direct à `document_key_belongs_to` (sans
    passer par `build_document_object_key`) avec un nom contenant "/"
    doit, lui aussi, toujours être refusé."""
    for build, belongs_to, resource_kwarg in _CASES:
        tenant_id = uuid.uuid4()
        resource_id = uuid.uuid4()
        prefix = build(
            tenant_id=tenant_id, filename="x.pdf", **{resource_kwarg: resource_id}
        ).rsplit("/", 1)[0]
        assert not belongs_to(
            f"{prefix}/sous-dossier/x.pdf", tenant_id=tenant_id, **{resource_kwarg: resource_id}
        )


def test_build_remplace_les_separateurs_du_nom_de_fichier():
    """`build_*` ne doit jamais laisser passer un "/" venu du nom de
    fichier fourni : c'est ce remplacement qui garantit que la partie nom
    de la clé construite reste un segment unique, sans quoi la propre
    protection de `*_key_belongs_to` (aucun "/" toléré) deviendrait inutile
    puisque le serveur lui-même aurait construit une clé invalide."""
    for build, belongs_to, resource_kwarg in _CASES:
        tenant_id = uuid.uuid4()
        resource_id = uuid.uuid4()
        key = build(
            tenant_id=tenant_id, filename="../../etc/passwd", **{resource_kwarg: resource_id}
        )
        last_segment = key.rsplit("/", 1)[-1]
        assert "/" not in last_segment
        assert belongs_to(key, tenant_id=tenant_id, **{resource_kwarg: resource_id})
