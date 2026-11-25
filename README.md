# OptiIA Planner V6

Installation : `pip install -r requirements.txt` puis `streamlit run app.py`.

- Akram et Igor : trois groupes chacun par défaut, les autres un groupe. Les engagements restent des hypothèses sauf indication contraire. B3 : charge réservée, dates inconnues.
- Les CM peuvent être répartis par bloc entre deux enseignants : cours 1–2 et cours 3–4 (Akram puis Igor, ou l’inverse). Les charges et les disponibilités tiennent compte de chaque séance. Les anciennes sauvegardes avec un seul enseignant par bloc restent lisibles.
- Tableau des charges, calendrier A–F (A par défaut), créneaux hypothétiques, indisponibilités.
- Le calcul tente un planning complet sans mutualisation TD/TP. Si aucun résultat complet n'est trouvé, il propose un planning partiel sur une répartition équilibrée des groupes. Les séances manquantes et heures restantes sont affichées. Les séances placées respectent leur ordre relatif ; compléter les prérequis manquants avant validation. Le résultat partiel n'est pas nécessairement optimal globalement.
- Sauvegarde automatique des paramètres valides et du planning correspondant dans `.local/scenario.json`, dans le dossier du projet. Le fichier est rechargé au redémarrage. Le bouton de réinitialisation supprime les données et remet les valeurs par défaut. Export/import JSON des paramètres pour transférer le travail. Ne pas partager ce fichier sans accord ; il contient les disponibilités et charges de l'équipe. Pas de sauvegarde collaborative ni de secrets enregistrés dans ce fichier.
- Export CSV. Publication Google Sheets bloquée en cas de planning incomplet, créneaux hypothétiques ou enseignants non confirmés. B3, contrôles et salles ne sont pas finalisés.

## Google Sheets
Créer un classeur, activer l'API Google Sheets et partager le classeur avec le compte de service. Copier `.streamlit/secrets.example.toml` vers `.streamlit/secrets.toml` et renseigner les valeurs. La publication remplace les valeurs de l'onglet dédié Planning E3 ; vérifier les autorisations et valider explicitement. Ne pas versionner les secrets.

## Vérifications
Compilation Python, sauvegarde/relecture/réinitialisation JSON et génération partielle testées. Interface Streamlit et connexion Google non testées dans l'environnement de création.
