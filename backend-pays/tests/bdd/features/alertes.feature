# language: fr
Feature: Gestion des alertes
  En tant que système de monitoring FutureKawa
  Je veux créer et consulter les alertes de dépassement de seuil
  Afin de réagir rapidement aux anomalies de stockage

  Scenario: Créer une alerte de température
    Given l'API FutureKawa est démarrée
    When je crée une alerte de type "temperature" avec message "Température trop élevée" et valeur 35.0
    Then la réponse a le statut 201
    And l'alerte a le statut "non_lue"

  Scenario: Lister les alertes non lues
    Given l'API FutureKawa est démarrée
    And une alerte non lue existe en base
    When je consulte la liste des alertes
    Then la réponse a le statut 200
    And la liste contient au moins une alerte

  Scenario: Marquer une alerte comme lue
    Given l'API FutureKawa est démarrée
    And une alerte non lue existe en base
    When je marque l'alerte comme lue
    Then la réponse a le statut 200
    And l'alerte a le statut "lue"
