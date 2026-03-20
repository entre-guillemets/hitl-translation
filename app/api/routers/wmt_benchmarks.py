from fastapi import APIRouter, Depends, HTTPException, Query
import logging
import random
import statistics
from typing import List, Dict, Any, Optional
from datetime import datetime
import sacrebleu
from prisma import Json

from app.schemas.wmt import WMTRequestCreate, WMTBenchmarkResult
from app.db.base import prisma
from app.services.translation_service import translation_service
from app.utils.text_processing import get_model_for_language_pair, detokenize_japanese
from app.utils.lang_pair import normalize_lang_pair
from app.dependencies import get_multi_engine_service, get_comet_model
from app.api.routers.quality_assessment import comet_predict

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/wmt", tags=["WMT Benchmarks"])

# Benchmark sentence pairs.
# EN↔FR and EN↔JP: representative WMT newstest sentences.
# EN↔SW: FLORES-200 devtest sentences (swh_Latn).
WMT_SAMPLE_DATA = {
    "en-fr": [
        {"source": "The cat sits on the mat.", "reference": "Le chat est assis sur le tapis."},
        {"source": "Hello, how are you today?", "reference": "Bonjour, comment allez-vous aujourd'hui ?"},
        {"source": "Machine translation has improved significantly.", "reference": "La traduction automatique s'est considérablement améliorée."},
        {"source": "The weather is beautiful today.", "reference": "Le temps est magnifique aujourd'hui."},
        {"source": "I would like to order a coffee.", "reference": "Je voudrais commander un café."},
        {"source": "Scientists have discovered a new species of deep-sea fish near the Pacific coast.", "reference": "Des scientifiques ont découvert une nouvelle espèce de poisson des grands fonds près de la côte pacifique."},
        {"source": "The government announced a series of economic reforms aimed at reducing unemployment.", "reference": "Le gouvernement a annoncé une série de réformes économiques visant à réduire le chômage."},
        {"source": "Renewable energy sources are becoming increasingly cost-competitive with fossil fuels.", "reference": "Les sources d'énergie renouvelables deviennent de plus en plus compétitives en termes de coût par rapport aux combustibles fossiles."},
        {"source": "The hospital reported a significant decline in emergency room wait times following staff increases.", "reference": "L'hôpital a signalé une diminution significative des temps d'attente aux urgences suite à des augmentations de personnel."},
        {"source": "Children who read regularly tend to develop stronger vocabulary and critical thinking skills.", "reference": "Les enfants qui lisent régulièrement ont tendance à développer un vocabulaire plus riche et de meilleures capacités de pensée critique."},
        {"source": "The new transit line will connect the city center to the international airport in under thirty minutes.", "reference": "La nouvelle ligne de transport reliera le centre-ville à l'aéroport international en moins de trente minutes."},
        {"source": "Researchers at the university have developed a biodegradable plastic alternative made from seaweed.", "reference": "Des chercheurs de l'université ont développé une alternative plastique biodégradable fabriquée à partir d'algues."},
        {"source": "The prime minister called for international cooperation to address the growing refugee crisis.", "reference": "Le premier ministre a appelé à une coopération internationale pour faire face à la crise croissante des réfugiés."},
        {"source": "Local farmers are adopting precision agriculture techniques to reduce water consumption.", "reference": "Les agriculteurs locaux adoptent des techniques d'agriculture de précision pour réduire la consommation d'eau."},
        {"source": "The museum's new exhibition explores the intersection of technology and contemporary art.", "reference": "La nouvelle exposition du musée explore l'intersection de la technologie et de l'art contemporain."},
        {"source": "A major earthquake struck the coastal region, triggering tsunami warnings across the Pacific.", "reference": "Un séisme majeur a frappé la région côtière, déclenchant des alertes au tsunami dans tout le Pacifique."},
        {"source": "The central bank raised interest rates for the third consecutive quarter to combat inflation.", "reference": "La banque centrale a relevé ses taux d'intérêt pour le troisième trimestre consécutif afin de lutter contre l'inflation."},
        {"source": "Electric vehicle sales surpassed those of traditional combustion engine cars for the first time.", "reference": "Les ventes de véhicules électriques ont dépassé celles des voitures à moteur à combustion traditionnelle pour la première fois."},
        {"source": "The company announced it would lay off fifteen percent of its global workforce following poor quarterly results.", "reference": "L'entreprise a annoncé qu'elle licencierait quinze pour cent de ses effectifs mondiaux suite à de mauvais résultats trimestriels."},
        {"source": "Astronomers have detected a potentially habitable exoplanet orbiting a nearby star system.", "reference": "Les astronomes ont détecté une exoplanète potentiellement habitable en orbite autour d'un système stellaire voisin."},
        {"source": "The new drug showed promising results in phase three clinical trials for the treatment of Alzheimer's disease.", "reference": "Le nouveau médicament a montré des résultats prometteurs lors des essais cliniques de phase trois pour le traitement de la maladie d'Alzheimer."},
        {"source": "Urban planners are redesigning city centers to prioritize pedestrians and cyclists over motor vehicles.", "reference": "Les urbanistes repensent les centres-villes pour donner la priorité aux piétons et aux cyclistes plutôt qu'aux véhicules motorisés."},
        {"source": "The film won the Palme d'Or at Cannes for its unflinching portrayal of social inequality.", "reference": "Le film a remporté la Palme d'Or à Cannes pour son portrait sans concession des inégalités sociales."},
        {"source": "Health authorities urged residents to get vaccinated ahead of the flu season.", "reference": "Les autorités sanitaires ont exhorté les résidents à se faire vacciner avant la saison grippale."},
        {"source": "The treaty negotiations broke down after the two sides failed to agree on territorial boundaries.", "reference": "Les négociations du traité ont échoué après que les deux parties n'ont pas réussi à s'entendre sur les frontières territoriales."},
        {"source": "Software developers are increasingly using artificial intelligence tools to accelerate code review.", "reference": "Les développeurs de logiciels utilisent de plus en plus des outils d'intelligence artificielle pour accélérer la révision du code."},
        {"source": "The drought has severely affected crop yields across the southern agricultural belt.", "reference": "La sécheresse a gravement affecté les rendements agricoles dans toute la ceinture agricole du sud."},
        {"source": "A coalition of environmental groups filed a lawsuit against the petrochemical plant over pollution concerns.", "reference": "Une coalition de groupes environnementaux a déposé une plainte contre l'usine pétrochimique en raison de préoccupations liées à la pollution."},
        {"source": "The opposition leader was arrested on charges of corruption and abuse of power.", "reference": "Le chef de l'opposition a été arrêté pour des accusations de corruption et d'abus de pouvoir."},
        {"source": "Surgeons successfully performed the world's first fully robotic heart transplant.", "reference": "Des chirurgiens ont réussi à réaliser la première transplantation cardiaque entièrement robotisée au monde."},
        {"source": "The central library will be renovated and expanded to include a digital media center.", "reference": "La bibliothèque centrale sera rénovée et agrandie pour inclure un centre de médias numériques."},
        {"source": "Inflation reached its highest level in four decades, squeezing household budgets across the country.", "reference": "L'inflation a atteint son niveau le plus élevé en quatre décennies, comprimant les budgets des ménages dans tout le pays."},
        {"source": "The national football team qualified for the World Cup after a dramatic penalty shootout.", "reference": "L'équipe nationale de football s'est qualifiée pour la Coupe du monde après une séance de tirs au but dramatique."},
        {"source": "New evidence suggests that regular physical activity can reduce the risk of developing dementia.", "reference": "De nouvelles preuves suggèrent que l'activité physique régulière peut réduire le risque de développer une démence."},
        {"source": "The startup secured fifty million dollars in venture capital funding to expand its operations internationally.", "reference": "La startup a obtenu cinquante millions de dollars de financement en capital-risque pour étendre ses activités à l'international."},
        {"source": "Wildfires have consumed more than half a million hectares of forest in the past month alone.", "reference": "Les feux de forêt ont consumé plus d'un demi-million d'hectares de forêt au cours du seul mois dernier."},
        {"source": "The archaeological excavation uncovered artifacts dating back more than three thousand years.", "reference": "La fouille archéologique a mis au jour des artefacts datant de plus de trois mille ans."},
        {"source": "Passengers on the delayed flight were offered hotel accommodation and meal vouchers by the airline.", "reference": "Les passagers du vol retardé se sont vu offrir un hébergement à l'hôtel et des bons repas par la compagnie aérienne."},
        {"source": "The new education policy requires all primary schools to offer coding classes from the age of seven.", "reference": "La nouvelle politique éducative exige que toutes les écoles primaires proposent des cours de programmation dès l'âge de sept ans."},
        {"source": "A record number of tourists visited the country last year, boosting the hospitality sector significantly.", "reference": "Un nombre record de touristes a visité le pays l'année dernière, stimulant considérablement le secteur de l'hôtellerie."},
        {"source": "The judge dismissed the case due to insufficient evidence presented by the prosecution.", "reference": "Le juge a rejeté l'affaire en raison des preuves insuffisantes présentées par le parquet."},
        {"source": "Scientists warn that ocean acidification poses a serious threat to coral reef ecosystems worldwide.", "reference": "Les scientifiques avertissent que l'acidification des océans constitue une menace sérieuse pour les écosystèmes des récifs coralliens dans le monde entier."},
        {"source": "The author's latest novel explores themes of identity and belonging in a multicultural society.", "reference": "Le dernier roman de l'auteur explore les thèmes de l'identité et de l'appartenance dans une société multiculturelle."},
        {"source": "Negotiations over the trade agreement have stalled amid disagreements over intellectual property rights.", "reference": "Les négociations sur l'accord commercial sont au point mort en raison de désaccords sur les droits de propriété intellectuelle."},
        {"source": "The charity raised over two million euros for disaster relief efforts in the affected regions.", "reference": "L'association a collecté plus de deux millions d'euros pour les efforts d'aide aux victimes de catastrophes dans les régions touchées."},
        {"source": "Satellite imagery confirms that the polar ice cap has shrunk to its smallest recorded extent.", "reference": "Les images satellites confirment que la calotte polaire a rétréci à son étendue la plus petite jamais enregistrée."},
        {"source": "The city council approved a new affordable housing development in the eastern district.", "reference": "Le conseil municipal a approuvé un nouveau projet de logements abordables dans le quartier est."},
        {"source": "Experts predict that quantum computing will revolutionize drug discovery within the next decade.", "reference": "Les experts prévoient que l'informatique quantique révolutionnera la découverte de médicaments au cours de la prochaine décennie."},
        {"source": "The protest march drew tens of thousands of participants calling for stronger climate action.", "reference": "La marche de protestation a rassemblé des dizaines de milliers de participants réclamant des mesures climatiques plus fortes."},
        {"source": "Authorities have launched an investigation into alleged financial misconduct at the state-owned enterprise.", "reference": "Les autorités ont lancé une enquête sur des allégations d'irrégularités financières au sein de l'entreprise publique."},
        {"source": "The refugee camp, which was intended to house five thousand people, now shelters over thirty thousand.", "reference": "Le camp de réfugiés, qui était censé accueillir cinq mille personnes, abrite désormais plus de trente mille."},
        {"source": "A new study links excessive screen time in adolescents to increased rates of anxiety and depression.", "reference": "Une nouvelle étude établit un lien entre le temps d'écran excessif chez les adolescents et l'augmentation des taux d'anxiété et de dépression."},
        {"source": "The orchestra performed Beethoven's Ninth Symphony to a sold-out audience at the concert hall.", "reference": "L'orchestre a interprété la Neuvième Symphonie de Beethoven devant un public qui a fait salle comble au concert."},
        {"source": "Border officials intercepted a shipment of counterfeit pharmaceuticals worth millions of dollars.", "reference": "Les agents des douanes ont intercepté une cargaison de produits pharmaceutiques contrefaits valant des millions de dollars."},
        {"source": "The merger between the two telecommunications giants is subject to regulatory approval in multiple jurisdictions.", "reference": "La fusion entre les deux géants des télécommunications est soumise à l'approbation réglementaire dans plusieurs juridictions."},
        {"source": "Community volunteers planted over ten thousand trees along the riverbank as part of a reforestation project.", "reference": "Des bénévoles communautaires ont planté plus de dix mille arbres le long de la rive dans le cadre d'un projet de reboisement."},
        {"source": "The prime suspect in the kidnapping case was apprehended at the international airport.", "reference": "Le principal suspect dans l'affaire d'enlèvement a été appréhendé à l'aéroport international."},
        {"source": "Food prices have surged following supply chain disruptions caused by the prolonged conflict.", "reference": "Les prix alimentaires ont augmenté en raison des perturbations de la chaîne d'approvisionnement causées par le conflit prolongé."},
        {"source": "The university has established a new research center dedicated to the study of artificial intelligence ethics.", "reference": "L'université a créé un nouveau centre de recherche dédié à l'étude de l'éthique de l'intelligence artificielle."},
        {"source": "A groundbreaking agreement between the two nations aims to eliminate trade tariffs within five years.", "reference": "Un accord novateur entre les deux nations vise à éliminer les droits de douane commerciaux dans un délai de cinq ans."},
        {"source": "The patient recovered fully after receiving a pioneering gene therapy treatment for the rare condition.", "reference": "Le patient s'est complètement rétabli après avoir reçu un traitement de thérapie génique pionnier pour la maladie rare."},
        {"source": "Heavy snowfall has paralyzed transport networks across the northern provinces.", "reference": "De fortes chutes de neige ont paralysé les réseaux de transport dans les provinces du nord."},
        {"source": "The tech giant faces antitrust scrutiny over its acquisition of a major cloud computing firm.", "reference": "Le géant technologique fait l'objet d'un examen antitrust concernant son acquisition d'une grande entreprise d'informatique en nuage."},
        {"source": "Local authorities are struggling to manage the influx of tourists during the peak summer season.", "reference": "Les autorités locales peinent à gérer l'afflux de touristes pendant la haute saison estivale."},
        {"source": "The documentary won international acclaim for its honest depiction of life in conflict zones.", "reference": "Le documentaire a remporté une reconnaissance internationale pour sa représentation honnête de la vie dans les zones de conflit."},
        {"source": "Engineers have designed a new bridge capable of withstanding category five hurricane winds.", "reference": "Des ingénieurs ont conçu un nouveau pont capable de résister aux vents d'un ouragan de catégorie cinq."},
        {"source": "The policy shift marks a significant departure from decades of established foreign relations doctrine.", "reference": "Le changement de politique marque un écart significatif par rapport à des décennies de doctrine établie en matière de relations étrangères."},
        {"source": "Volunteers from across the country converged on the flood-hit town to assist with cleanup efforts.", "reference": "Des bénévoles de tout le pays ont convergé vers la ville sinistrée par les inondations pour aider aux efforts de nettoyage."},
        {"source": "The clinical trial enrolled over two thousand participants across twelve research hospitals.", "reference": "L'essai clinique a recruté plus de deux mille participants dans douze hôpitaux de recherche."},
        {"source": "The architecture firm won the commission to design the new national library building.", "reference": "Le cabinet d'architecture a remporté le contrat pour concevoir le nouveau bâtiment de la bibliothèque nationale."},
        {"source": "Rising sea levels threaten to submerge low-lying island nations within the next fifty years.", "reference": "La montée du niveau de la mer menace d'engloutir les nations insulaires de basse altitude dans les cinquante prochaines années."},
        {"source": "The airline introduced a new direct route connecting the two major business hubs.", "reference": "La compagnie aérienne a introduit une nouvelle liaison directe reliant les deux grands pôles d'affaires."},
        {"source": "Critics praised the novel for its nuanced portrayal of generational trauma and cultural displacement.", "reference": "Les critiques ont salué le roman pour sa représentation nuancée du traumatisme générationnel et du déplacement culturel."},
        {"source": "The summit of world leaders produced a joint declaration on nuclear disarmament.", "reference": "Le sommet des dirigeants mondiaux a produit une déclaration commune sur le désarmement nucléaire."},
        {"source": "Biologists have mapped the genome of a previously unknown organism found in deep ocean sediment.", "reference": "Des biologistes ont cartographié le génome d'un organisme inconnu jusqu'alors, trouvé dans les sédiments des grands fonds océaniques."},
        {"source": "The retail sector reported its weakest quarterly performance in over a decade.", "reference": "Le secteur de la distribution a enregistré ses performances trimestrielles les plus faibles depuis plus d'une décennie."},
        {"source": "Teachers are calling for smaller class sizes to improve educational outcomes.", "reference": "Les enseignants réclament des classes moins chargées pour améliorer les résultats scolaires."},
        {"source": "The opposition party secured enough seats in parliament to form a minority government.", "reference": "Le parti d'opposition a obtenu suffisamment de sièges au parlement pour former un gouvernement minoritaire."},
        {"source": "A new report highlights significant gender pay gaps across the technology and finance sectors.", "reference": "Un nouveau rapport met en évidence des écarts de rémunération significatifs entre les sexes dans les secteurs de la technologie et de la finance."},
        {"source": "The ancient manuscript was digitized and made publicly available online for the first time.", "reference": "Le manuscrit ancien a été numérisé et rendu publiquement accessible en ligne pour la première fois."},
        {"source": "Manufacturers are facing shortages of key semiconductor components due to ongoing supply chain disruptions.", "reference": "Les fabricants font face à des pénuries de composants semiconducteurs clés en raison de perturbations persistantes de la chaîne d'approvisionnement."},
        {"source": "The cycling team completed the grueling mountain stage in record time despite adverse weather conditions.", "reference": "L'équipe cycliste a terminé l'étape de montagne éprouvante en un temps record malgré des conditions météorologiques défavorables."},
        {"source": "Data privacy advocates are pushing for stricter regulations on the collection of personal information.", "reference": "Les défenseurs de la vie privée des données plaident pour des réglementations plus strictes sur la collecte d'informations personnelles."},
        {"source": "The conservation project successfully reintroduced a population of wolves to the national park.", "reference": "Le projet de conservation a réussi à réintroduire une population de loups dans le parc national."},
        {"source": "The finance minister presented the annual budget amid growing concerns over public debt levels.", "reference": "Le ministre des finances a présenté le budget annuel dans un contexte de préoccupations croissantes concernant les niveaux d'endettement public."},
        {"source": "Authorities have issued a public health advisory following the outbreak of a respiratory illness.", "reference": "Les autorités ont émis un avis de santé publique à la suite d'une épidémie de maladie respiratoire."},
        {"source": "The solar power plant will generate enough electricity to supply over one hundred thousand homes.", "reference": "La centrale solaire produira suffisamment d'électricité pour alimenter plus de cent mille foyers."},
        {"source": "Prison reform advocates argue that rehabilitation programs reduce recidivism more effectively than harsher sentences.", "reference": "Les défenseurs de la réforme pénitentiaire soutiennent que les programmes de réhabilitation réduisent la récidive plus efficacement que les peines plus sévères."},
        {"source": "The foreign minister met with her counterpart to discuss bilateral trade and security cooperation.", "reference": "La ministre des affaires étrangères a rencontré son homologue pour discuter du commerce bilatéral et de la coopération en matière de sécurité."},
        {"source": "The smartphone manufacturer unveiled its latest flagship device with an improved camera system.", "reference": "Le fabricant de smartphones a dévoilé son dernier appareil phare doté d'un système de caméra amélioré."},
        {"source": "A landslide buried several homes in the mountainous village following days of heavy rainfall.", "reference": "Un glissement de terrain a enseveli plusieurs maisons dans le village montagnard après des jours de pluies torrentielles."},
        {"source": "The central bank intervened in currency markets to stabilize the rapidly depreciating exchange rate.", "reference": "La banque centrale est intervenue sur les marchés des changes pour stabiliser le taux de change en forte dépréciation."},
        {"source": "Genetic research has shed new light on the migration patterns of early human populations.", "reference": "La recherche génétique a apporté un nouvel éclairage sur les schémas de migration des premières populations humaines."},
        {"source": "The city's public housing shortage has driven up rental prices and displaced many low-income families.", "reference": "La pénurie de logements sociaux dans la ville a fait monter les loyers et déplacé de nombreuses familles à faibles revenus."},
        {"source": "International observers declared the election results credible despite opposition claims of irregularities.", "reference": "Les observateurs internationaux ont déclaré les résultats électoraux crédibles malgré les allégations d'irrégularités de l'opposition."},
    ],

    "fr-en": [
        {"source": "Le chat est assis sur le tapis.", "reference": "The cat sits on the mat."},
        {"source": "Bonjour, comment allez-vous ?", "reference": "Hello, how are you?"},
        {"source": "La traduction automatique s'améliore.", "reference": "Machine translation is improving."},
        {"source": "Il fait beau aujourd'hui.", "reference": "The weather is nice today."},
        {"source": "Je voudrais un café, s'il vous plaît.", "reference": "I would like a coffee, please."},
        {"source": "Des scientifiques ont découvert une nouvelle espèce de poisson des grands fonds près de la côte pacifique.", "reference": "Scientists have discovered a new species of deep-sea fish near the Pacific coast."},
        {"source": "Le gouvernement a annoncé une série de réformes économiques visant à réduire le chômage.", "reference": "The government announced a series of economic reforms aimed at reducing unemployment."},
        {"source": "Les sources d'énergie renouvelables deviennent de plus en plus compétitives en termes de coût par rapport aux combustibles fossiles.", "reference": "Renewable energy sources are becoming increasingly cost-competitive with fossil fuels."},
        {"source": "L'hôpital a signalé une diminution significative des temps d'attente aux urgences suite à des augmentations de personnel.", "reference": "The hospital reported a significant decline in emergency room wait times following staff increases."},
        {"source": "Les enfants qui lisent régulièrement ont tendance à développer un vocabulaire plus riche et de meilleures capacités de pensée critique.", "reference": "Children who read regularly tend to develop stronger vocabulary and critical thinking skills."},
        {"source": "La nouvelle ligne de transport reliera le centre-ville à l'aéroport international en moins de trente minutes.", "reference": "The new transit line will connect the city center to the international airport in under thirty minutes."},
        {"source": "Des chercheurs de l'université ont développé une alternative plastique biodégradable fabriquée à partir d'algues.", "reference": "Researchers at the university have developed a biodegradable plastic alternative made from seaweed."},
        {"source": "Le premier ministre a appelé à une coopération internationale pour faire face à la crise croissante des réfugiés.", "reference": "The prime minister called for international cooperation to address the growing refugee crisis."},
        {"source": "Les agriculteurs locaux adoptent des techniques d'agriculture de précision pour réduire la consommation d'eau.", "reference": "Local farmers are adopting precision agriculture techniques to reduce water consumption."},
        {"source": "La nouvelle exposition du musée explore l'intersection de la technologie et de l'art contemporain.", "reference": "The museum's new exhibition explores the intersection of technology and contemporary art."},
        {"source": "Un séisme majeur a frappé la région côtière, déclenchant des alertes au tsunami dans tout le Pacifique.", "reference": "A major earthquake struck the coastal region, triggering tsunami warnings across the Pacific."},
        {"source": "La banque centrale a relevé ses taux d'intérêt pour le troisième trimestre consécutif afin de lutter contre l'inflation.", "reference": "The central bank raised interest rates for the third consecutive quarter to combat inflation."},
        {"source": "Les ventes de véhicules électriques ont dépassé celles des voitures à moteur à combustion traditionnelle pour la première fois.", "reference": "Electric vehicle sales surpassed those of traditional combustion engine cars for the first time."},
        {"source": "L'entreprise a annoncé qu'elle licencierait quinze pour cent de ses effectifs mondiaux suite à de mauvais résultats trimestriels.", "reference": "The company announced it would lay off fifteen percent of its global workforce following poor quarterly results."},
        {"source": "Les astronomes ont détecté une exoplanète potentiellement habitable en orbite autour d'un système stellaire voisin.", "reference": "Astronomers have detected a potentially habitable exoplanet orbiting a nearby star system."},
        {"source": "Le nouveau médicament a montré des résultats prometteurs lors des essais cliniques de phase trois pour le traitement de la maladie d'Alzheimer.", "reference": "The new drug showed promising results in phase three clinical trials for the treatment of Alzheimer's disease."},
        {"source": "Les urbanistes repensent les centres-villes pour donner la priorité aux piétons et aux cyclistes plutôt qu'aux véhicules motorisés.", "reference": "Urban planners are redesigning city centers to prioritize pedestrians and cyclists over motor vehicles."},
        {"source": "Le film a remporté la Palme d'Or à Cannes pour son portrait sans concession des inégalités sociales.", "reference": "The film won the Palme d'Or at Cannes for its unflinching portrayal of social inequality."},
        {"source": "Les autorités sanitaires ont exhorté les résidents à se faire vacciner avant la saison grippale.", "reference": "Health authorities urged residents to get vaccinated ahead of the flu season."},
        {"source": "Les négociations du traité ont échoué après que les deux parties n'ont pas réussi à s'entendre sur les frontières territoriales.", "reference": "The treaty negotiations broke down after the two sides failed to agree on territorial boundaries."},
        {"source": "Les développeurs de logiciels utilisent de plus en plus des outils d'intelligence artificielle pour accélérer la révision du code.", "reference": "Software developers are increasingly using artificial intelligence tools to accelerate code review."},
        {"source": "La sécheresse a gravement affecté les rendements agricoles dans toute la ceinture agricole du sud.", "reference": "The drought has severely affected crop yields across the southern agricultural belt."},
        {"source": "Une coalition de groupes environnementaux a déposé une plainte contre l'usine pétrochimique en raison de préoccupations liées à la pollution.", "reference": "A coalition of environmental groups filed a lawsuit against the petrochemical plant over pollution concerns."},
        {"source": "Le chef de l'opposition a été arrêté pour des accusations de corruption et d'abus de pouvoir.", "reference": "The opposition leader was arrested on charges of corruption and abuse of power."},
        {"source": "Des chirurgiens ont réussi à réaliser la première transplantation cardiaque entièrement robotisée au monde.", "reference": "Surgeons successfully performed the world's first fully robotic heart transplant."},
        {"source": "La bibliothèque centrale sera rénovée et agrandie pour inclure un centre de médias numériques.", "reference": "The central library will be renovated and expanded to include a digital media center."},
        {"source": "L'inflation a atteint son niveau le plus élevé en quatre décennies, comprimant les budgets des ménages dans tout le pays.", "reference": "Inflation reached its highest level in four decades, squeezing household budgets across the country."},
        {"source": "L'équipe nationale de football s'est qualifiée pour la Coupe du monde après une séance de tirs au but dramatique.", "reference": "The national football team qualified for the World Cup after a dramatic penalty shootout."},
        {"source": "De nouvelles preuves suggèrent que l'activité physique régulière peut réduire le risque de développer une démence.", "reference": "New evidence suggests that regular physical activity can reduce the risk of developing dementia."},
        {"source": "La startup a obtenu cinquante millions de dollars de financement en capital-risque pour étendre ses activités à l'international.", "reference": "The startup secured fifty million dollars in venture capital funding to expand its operations internationally."},
        {"source": "Les feux de forêt ont consumé plus d'un demi-million d'hectares de forêt au cours du seul mois dernier.", "reference": "Wildfires have consumed more than half a million hectares of forest in the past month alone."},
        {"source": "La fouille archéologique a mis au jour des artefacts datant de plus de trois mille ans.", "reference": "The archaeological excavation uncovered artifacts dating back more than three thousand years."},
        {"source": "Les passagers du vol retardé se sont vu offrir un hébergement à l'hôtel et des bons repas par la compagnie aérienne.", "reference": "Passengers on the delayed flight were offered hotel accommodation and meal vouchers by the airline."},
        {"source": "La nouvelle politique éducative exige que toutes les écoles primaires proposent des cours de programmation dès l'âge de sept ans.", "reference": "The new education policy requires all primary schools to offer coding classes from the age of seven."},
        {"source": "Un nombre record de touristes a visité le pays l'année dernière, stimulant considérablement le secteur de l'hôtellerie.", "reference": "A record number of tourists visited the country last year, boosting the hospitality sector significantly."},
        {"source": "Le juge a rejeté l'affaire en raison des preuves insuffisantes présentées par le parquet.", "reference": "The judge dismissed the case due to insufficient evidence presented by the prosecution."},
        {"source": "Les scientifiques avertissent que l'acidification des océans constitue une menace sérieuse pour les écosystèmes des récifs coralliens dans le monde entier.", "reference": "Scientists warn that ocean acidification poses a serious threat to coral reef ecosystems worldwide."},
        {"source": "Le dernier roman de l'auteur explore les thèmes de l'identité et de l'appartenance dans une société multiculturelle.", "reference": "The author's latest novel explores themes of identity and belonging in a multicultural society."},
        {"source": "Les négociations sur l'accord commercial sont au point mort en raison de désaccords sur les droits de propriété intellectuelle.", "reference": "Negotiations over the trade agreement have stalled amid disagreements over intellectual property rights."},
        {"source": "L'association a collecté plus de deux millions d'euros pour les efforts d'aide aux victimes de catastrophes dans les régions touchées.", "reference": "The charity raised over two million euros for disaster relief efforts in the affected regions."},
        {"source": "Les images satellites confirment que la calotte polaire a rétréci à son étendue la plus petite jamais enregistrée.", "reference": "Satellite imagery confirms that the polar ice cap has shrunk to its smallest recorded extent."},
        {"source": "Le conseil municipal a approuvé un nouveau projet de logements abordables dans le quartier est.", "reference": "The city council approved a new affordable housing development in the eastern district."},
        {"source": "Les experts prévoient que l'informatique quantique révolutionnera la découverte de médicaments au cours de la prochaine décennie.", "reference": "Experts predict that quantum computing will revolutionize drug discovery within the next decade."},
        {"source": "La marche de protestation a rassemblé des dizaines de milliers de participants réclamant des mesures climatiques plus fortes.", "reference": "The protest march drew tens of thousands of participants calling for stronger climate action."},
        {"source": "Les autorités ont lancé une enquête sur des allégations d'irrégularités financières au sein de l'entreprise publique.", "reference": "Authorities have launched an investigation into alleged financial misconduct at the state-owned enterprise."},
        {"source": "Le camp de réfugiés, qui était censé accueillir cinq mille personnes, abrite désormais plus de trente mille.", "reference": "The refugee camp, which was intended to house five thousand people, now shelters over thirty thousand."},
        {"source": "Une nouvelle étude établit un lien entre le temps d'écran excessif chez les adolescents et l'augmentation des taux d'anxiété et de dépression.", "reference": "A new study links excessive screen time in adolescents to increased rates of anxiety and depression."},
        {"source": "L'orchestre a interprété la Neuvième Symphonie de Beethoven devant un public qui a fait salle comble au concert.", "reference": "The orchestra performed Beethoven's Ninth Symphony to a sold-out audience at the concert hall."},
        {"source": "Les agents des douanes ont intercepté une cargaison de produits pharmaceutiques contrefaits valant des millions de dollars.", "reference": "Border officials intercepted a shipment of counterfeit pharmaceuticals worth millions of dollars."},
        {"source": "La fusion entre les deux géants des télécommunications est soumise à l'approbation réglementaire dans plusieurs juridictions.", "reference": "The merger between the two telecommunications giants is subject to regulatory approval in multiple jurisdictions."},
        {"source": "Des bénévoles communautaires ont planté plus de dix mille arbres le long de la rive dans le cadre d'un projet de reboisement.", "reference": "Community volunteers planted over ten thousand trees along the riverbank as part of a reforestation project."},
        {"source": "Le principal suspect dans l'affaire d'enlèvement a été appréhendé à l'aéroport international.", "reference": "The prime suspect in the kidnapping case was apprehended at the international airport."},
        {"source": "Les prix alimentaires ont augmenté en raison des perturbations de la chaîne d'approvisionnement causées par le conflit prolongé.", "reference": "Food prices have surged following supply chain disruptions caused by the prolonged conflict."},
        {"source": "L'université a créé un nouveau centre de recherche dédié à l'étude de l'éthique de l'intelligence artificielle.", "reference": "The university has established a new research center dedicated to the study of artificial intelligence ethics."},
        {"source": "Un accord novateur entre les deux nations vise à éliminer les droits de douane commerciaux dans un délai de cinq ans.", "reference": "A groundbreaking agreement between the two nations aims to eliminate trade tariffs within five years."},
        {"source": "Le patient s'est complètement rétabli après avoir reçu un traitement de thérapie génique pionnier pour la maladie rare.", "reference": "The patient recovered fully after receiving a pioneering gene therapy treatment for the rare condition."},
        {"source": "De fortes chutes de neige ont paralysé les réseaux de transport dans les provinces du nord.", "reference": "Heavy snowfall has paralyzed transport networks across the northern provinces."},
        {"source": "Le géant technologique fait l'objet d'un examen antitrust concernant son acquisition d'une grande entreprise d'informatique en nuage.", "reference": "The tech giant faces antitrust scrutiny over its acquisition of a major cloud computing firm."},
        {"source": "Les autorités locales peinent à gérer l'afflux de touristes pendant la haute saison estivale.", "reference": "Local authorities are struggling to manage the influx of tourists during the peak summer season."},
        {"source": "Le documentaire a remporté une reconnaissance internationale pour sa représentation honnête de la vie dans les zones de conflit.", "reference": "The documentary won international acclaim for its honest depiction of life in conflict zones."},
        {"source": "Des ingénieurs ont conçu un nouveau pont capable de résister aux vents d'un ouragan de catégorie cinq.", "reference": "Engineers have designed a new bridge capable of withstanding category five hurricane winds."},
        {"source": "Le changement de politique marque un écart significatif par rapport à des décennies de doctrine établie en matière de relations étrangères.", "reference": "The policy shift marks a significant departure from decades of established foreign relations doctrine."},
        {"source": "Des bénévoles de tout le pays ont convergé vers la ville sinistrée par les inondations pour aider aux efforts de nettoyage.", "reference": "Volunteers from across the country converged on the flood-hit town to assist with cleanup efforts."},
        {"source": "L'essai clinique a recruté plus de deux mille participants dans douze hôpitaux de recherche.", "reference": "The clinical trial enrolled over two thousand participants across twelve research hospitals."},
        {"source": "Le cabinet d'architecture a remporté le contrat pour concevoir le nouveau bâtiment de la bibliothèque nationale.", "reference": "The architecture firm won the commission to design the new national library building."},
        {"source": "La montée du niveau de la mer menace d'engloutir les nations insulaires de basse altitude dans les cinquante prochaines années.", "reference": "Rising sea levels threaten to submerge low-lying island nations within the next fifty years."},
        {"source": "La compagnie aérienne a introduit une nouvelle liaison directe reliant les deux grands pôles d'affaires.", "reference": "The airline introduced a new direct route connecting the two major business hubs."},
        {"source": "Les critiques ont salué le roman pour sa représentation nuancée du traumatisme générationnel et du déplacement culturel.", "reference": "Critics praised the novel for its nuanced portrayal of generational trauma and cultural displacement."},
        {"source": "Le sommet des dirigeants mondiaux a produit une déclaration commune sur le désarmement nucléaire.", "reference": "The summit of world leaders produced a joint declaration on nuclear disarmament."},
        {"source": "Des biologistes ont cartographié le génome d'un organisme inconnu jusqu'alors, trouvé dans les sédiments des grands fonds océaniques.", "reference": "Biologists have mapped the genome of a previously unknown organism found in deep ocean sediment."},
        {"source": "Le secteur de la distribution a enregistré ses performances trimestrielles les plus faibles depuis plus d'une décennie.", "reference": "The retail sector reported its weakest quarterly performance in over a decade."},
        {"source": "Les enseignants réclament des classes moins chargées pour améliorer les résultats scolaires.", "reference": "Teachers are calling for smaller class sizes to improve educational outcomes."},
        {"source": "Le parti d'opposition a obtenu suffisamment de sièges au parlement pour former un gouvernement minoritaire.", "reference": "The opposition party secured enough seats in parliament to form a minority government."},
        {"source": "Un nouveau rapport met en évidence des écarts de rémunération significatifs entre les sexes dans les secteurs de la technologie et de la finance.", "reference": "A new report highlights significant gender pay gaps across the technology and finance sectors."},
        {"source": "Le manuscrit ancien a été numérisé et rendu publiquement accessible en ligne pour la première fois.", "reference": "The ancient manuscript was digitized and made publicly available online for the first time."},
        {"source": "Les fabricants font face à des pénuries de composants semiconducteurs clés en raison de perturbations persistantes de la chaîne d'approvisionnement.", "reference": "Manufacturers are facing shortages of key semiconductor components due to ongoing supply chain disruptions."},
        {"source": "L'équipe cycliste a terminé l'étape de montagne éprouvante en un temps record malgré des conditions météorologiques défavorables.", "reference": "The cycling team completed the grueling mountain stage in record time despite adverse weather conditions."},
        {"source": "Les défenseurs de la vie privée des données plaident pour des réglementations plus strictes sur la collecte d'informations personnelles.", "reference": "Data privacy advocates are pushing for stricter regulations on the collection of personal information."},
        {"source": "Le projet de conservation a réussi à réintroduire une population de loups dans le parc national.", "reference": "The conservation project successfully reintroduced a population of wolves to the national park."},
        {"source": "Le ministre des finances a présenté le budget annuel dans un contexte de préoccupations croissantes concernant les niveaux d'endettement public.", "reference": "The finance minister presented the annual budget amid growing concerns over public debt levels."},
        {"source": "Les autorités ont émis un avis de santé publique à la suite d'une épidémie de maladie respiratoire.", "reference": "Authorities have issued a public health advisory following the outbreak of a respiratory illness."},
        {"source": "La centrale solaire produira suffisamment d'électricité pour alimenter plus de cent mille foyers.", "reference": "The solar power plant will generate enough electricity to supply over one hundred thousand homes."},
        {"source": "Les défenseurs de la réforme pénitentiaire soutiennent que les programmes de réhabilitation réduisent la récidive plus efficacement que les peines plus sévères.", "reference": "Prison reform advocates argue that rehabilitation programs reduce recidivism more effectively than harsher sentences."},
        {"source": "La ministre des affaires étrangères a rencontré son homologue pour discuter du commerce bilatéral et de la coopération en matière de sécurité.", "reference": "The foreign minister met with her counterpart to discuss bilateral trade and security cooperation."},
        {"source": "Le fabricant de smartphones a dévoilé son dernier appareil phare doté d'un système de caméra amélioré.", "reference": "The smartphone manufacturer unveiled its latest flagship device with an improved camera system."},
        {"source": "Un glissement de terrain a enseveli plusieurs maisons dans le village montagnard après des jours de pluies torrentielles.", "reference": "A landslide buried several homes in the mountainous village following days of heavy rainfall."},
        {"source": "La banque centrale est intervenue sur les marchés des changes pour stabiliser le taux de change en forte dépréciation.", "reference": "The central bank intervened in currency markets to stabilize the rapidly depreciating exchange rate."},
        {"source": "La recherche génétique a apporté un nouvel éclairage sur les schémas de migration des premières populations humaines.", "reference": "Genetic research has shed new light on the migration patterns of early human populations."},
        {"source": "La pénurie de logements sociaux dans la ville a fait monter les loyers et déplacé de nombreuses familles à faibles revenus.", "reference": "The city's public housing shortage has driven up rental prices and displaced many low-income families."},
        {"source": "Les observateurs internationaux ont déclaré les résultats électoraux crédibles malgré les allégations d'irrégularités de l'opposition.", "reference": "International observers declared the election results credible despite opposition claims of irregularities."},
    ],

    "en-jp": [
        {"source": "The cat sits on the mat.", "reference": "猫がマットの上に座っています。"},
        {"source": "Hello, how are you?", "reference": "こんにちは、元気ですか？"},
        {"source": "Machine translation technology is advancing.", "reference": "機械翻訳技術が進歩しています。"},
        {"source": "Today is a beautiful day.", "reference": "今日は美しい日です。"},
        {"source": "I want to learn Japanese.", "reference": "日本語を学びたいです。"},
        {"source": "Scientists have discovered a new species of deep-sea fish.", "reference": "科学者たちが新種の深海魚を発見しました。"},
        {"source": "The government announced economic reforms to reduce unemployment.", "reference": "政府は失業率を下げるための経済改革を発表しました。"},
        {"source": "Renewable energy is becoming more affordable.", "reference": "再生可能エネルギーがより手頃になってきています。"},
        {"source": "The hospital reported shorter emergency room wait times.", "reference": "病院は救急室の待ち時間が短縮されたと報告しました。"},
        {"source": "Children who read regularly develop stronger vocabulary.", "reference": "定期的に読書する子供たちはより豊かな語彙を身につけます。"},
        {"source": "The new transit line will connect downtown to the airport.", "reference": "新しい交通路線が市内中心部と空港を結ぶ予定です。"},
        {"source": "Researchers developed a biodegradable plastic alternative from seaweed.", "reference": "研究者たちが海藻から生分解性プラスチックの代替品を開発しました。"},
        {"source": "The prime minister called for international cooperation on refugees.", "reference": "首相は難民問題に関する国際協力を求めました。"},
        {"source": "Local farmers are using precision agriculture to save water.", "reference": "地元の農家は水を節約するために精密農業を活用しています。"},
        {"source": "The museum exhibition explores technology and contemporary art.", "reference": "美術館の展覧会では技術と現代アートの交差点を探求しています。"},
        {"source": "An earthquake triggered tsunami warnings across the Pacific.", "reference": "地震が太平洋全域に津波警報を引き起こしました。"},
        {"source": "The central bank raised interest rates to combat inflation.", "reference": "中央銀行はインフレに対抗するために金利を引き上げました。"},
        {"source": "Electric vehicle sales surpassed combustion engine cars for the first time.", "reference": "電気自動車の販売台数が初めて内燃機関車を上回りました。"},
        {"source": "The company will lay off fifteen percent of its global workforce.", "reference": "同社は世界の従業員の15パーセントを解雇する予定です。"},
        {"source": "Astronomers detected a potentially habitable exoplanet.", "reference": "天文学者たちが生命居住可能な可能性のある系外惑星を検出しました。"},
        {"source": "The new drug showed promising results for Alzheimer's treatment.", "reference": "新しい薬がアルツハイマー病の治療に有望な結果を示しました。"},
        {"source": "Urban planners are redesigning cities to prioritize pedestrians.", "reference": "都市計画家たちは歩行者を優先するために都市を再設計しています。"},
        {"source": "The film won the top prize at the international film festival.", "reference": "その映画は国際映画祭で最高賞を受賞しました。"},
        {"source": "Health authorities urged residents to get vaccinated before flu season.", "reference": "保健当局はインフルエンザシーズン前に住民にワクチン接種を促しました。"},
        {"source": "Treaty negotiations collapsed over disagreements on borders.", "reference": "国境問題での意見の相違から条約交渉が決裂しました。"},
        {"source": "Software developers use artificial intelligence to speed up code review.", "reference": "ソフトウェア開発者はコードレビューを高速化するために人工知能を活用しています。"},
        {"source": "The drought severely affected crop yields in the southern region.", "reference": "干ばつが南部地域の農作物の収穫量に深刻な影響を与えました。"},
        {"source": "Environmental groups filed a lawsuit against the petrochemical plant.", "reference": "環境団体が石油化学工場に対して訴訟を起こしました。"},
        {"source": "The opposition leader was arrested on corruption charges.", "reference": "野党指導者が汚職の罪で逮捕されました。"},
        {"source": "Surgeons performed the world's first fully robotic heart transplant.", "reference": "外科医たちが世界初の完全ロボット心臓移植手術を行いました。"},
        {"source": "The central library will be renovated to include a digital media center.", "reference": "中央図書館はデジタルメディアセンターを含む形に改装されます。"},
        {"source": "Inflation reached its highest level in four decades.", "reference": "インフレが40年ぶりの最高水準に達しました。"},
        {"source": "The national football team qualified for the World Cup.", "reference": "国内サッカーチームがワールドカップ出場権を獲得しました。"},
        {"source": "Regular physical activity can reduce the risk of dementia.", "reference": "定期的な運動は認知症のリスクを軽減できます。"},
        {"source": "The startup secured fifty million dollars in venture capital funding.", "reference": "そのスタートアップは5000万ドルのベンチャーキャピタル資金を調達しました。"},
        {"source": "Wildfires consumed more than half a million hectares of forest.", "reference": "山火事が50万ヘクタール以上の森林を焼き尽くしました。"},
        {"source": "The archaeological excavation uncovered three-thousand-year-old artifacts.", "reference": "考古学的発掘調査で3000年前の遺物が発見されました。"},
        {"source": "Passengers on the delayed flight received hotel accommodation from the airline.", "reference": "遅延した便の乗客は航空会社からホテルの宿泊を提供されました。"},
        {"source": "The new education policy requires coding classes from age seven.", "reference": "新しい教育政策では7歳からコーディングの授業が必修となります。"},
        {"source": "A record number of tourists visited the country last year.", "reference": "昨年、過去最多の観光客が訪れました。"},
        {"source": "The judge dismissed the case due to insufficient evidence.", "reference": "裁判官は証拠不十分を理由に訴訟を却下しました。"},
        {"source": "Ocean acidification poses a serious threat to coral reef ecosystems.", "reference": "海洋酸性化はサンゴ礁の生態系に深刻な脅威をもたらしています。"},
        {"source": "The author's novel explores identity in a multicultural society.", "reference": "その著者の小説は多文化社会におけるアイデンティティを探求しています。"},
        {"source": "Trade agreement negotiations stalled over intellectual property rights.", "reference": "知的財産権をめぐる対立から貿易協定交渉が行き詰まりました。"},
        {"source": "The charity raised two million euros for disaster relief.", "reference": "その慈善団体は災害救援のために200万ユーロを集めました。"},
        {"source": "Satellite imagery confirms the polar ice cap has shrunk.", "reference": "衛星画像により北極の氷床が縮小していることが確認されました。"},
        {"source": "The city council approved a new affordable housing development.", "reference": "市議会が新しい低価格住宅開発を承認しました。"},
        {"source": "Quantum computing will revolutionize drug discovery within a decade.", "reference": "量子コンピューティングは10年以内に創薬に革命をもたらすでしょう。"},
        {"source": "The protest march drew tens of thousands calling for climate action.", "reference": "抗議行進には気候変動対策を求める数万人が参加しました。"},
        {"source": "Authorities launched an investigation into financial misconduct.", "reference": "当局が不正行為に関する調査を開始しました。"},
        {"source": "The refugee camp now shelters thirty thousand people.", "reference": "その難民キャンプは現在3万人を収容しています。"},
        {"source": "Excessive screen time is linked to anxiety and depression in teenagers.", "reference": "過度なスクリーンタイムは10代の不安やうつ病と関連しています。"},
        {"source": "The orchestra performed Beethoven's Ninth to a sold-out crowd.", "reference": "オーケストラは満員の観衆の前でベートーヴェンの第9番を演奏しました。"},
        {"source": "Border officials intercepted counterfeit pharmaceutical shipments.", "reference": "国境警備員が偽造医薬品の積荷を押収しました。"},
        {"source": "The telecom merger is subject to regulatory approval in multiple countries.", "reference": "通信会社の合併は複数の国での規制当局の承認が必要です。"},
        {"source": "Volunteers planted ten thousand trees along the riverbank.", "reference": "ボランティアが川岸に1万本の木を植えました。"},
        {"source": "The kidnapping suspect was apprehended at the international airport.", "reference": "誘拐事件の容疑者が国際空港で逮捕されました。"},
        {"source": "Food prices surged following supply chain disruptions from the conflict.", "reference": "紛争による供給網の混乱から食料価格が急騰しました。"},
        {"source": "The university established a center for artificial intelligence ethics.", "reference": "大学が人工知能倫理のセンターを設立しました。"},
        {"source": "The two nations agreed to eliminate trade tariffs within five years.", "reference": "両国は5年以内に関税を撤廃することで合意しました。"},
        {"source": "The patient recovered after receiving pioneering gene therapy.", "reference": "患者は先駆的な遺伝子治療を受けた後に回復しました。"},
        {"source": "Heavy snowfall paralyzed transport networks across the northern provinces.", "reference": "大雪が北部の交通網を麻痺させました。"},
        {"source": "The tech giant faces antitrust scrutiny over its cloud computing acquisition.", "reference": "大手テクノロジー企業がクラウドコンピューティング企業の買収に関して独占禁止法の審査を受けています。"},
        {"source": "Local authorities are struggling to manage tourist influx during peak season.", "reference": "地元当局はピークシーズンの観光客の急増への対応に苦慮しています。"},
        {"source": "The documentary won international acclaim for depicting life in conflict zones.", "reference": "そのドキュメンタリーは紛争地帯の生活を描いたことで国際的な賞賛を得ました。"},
        {"source": "Engineers designed a bridge capable of withstanding category five hurricanes.", "reference": "エンジニアたちがカテゴリー5のハリケーンに耐えられる橋を設計しました。"},
        {"source": "The policy shift departs from decades of established foreign relations doctrine.", "reference": "この政策転換は数十年にわたって確立された外交政策から大きく逸脱しています。"},
        {"source": "Volunteers converged on the flood-hit town to assist with cleanup.", "reference": "ボランティアが洪水被害を受けた町に集まり、清掃作業を支援しました。"},
        {"source": "The clinical trial enrolled two thousand participants across twelve hospitals.", "reference": "臨床試験では12の病院で2000人の参加者が登録されました。"},
        {"source": "The architecture firm won the contract to design the national library.", "reference": "その建築事務所が国立図書館の設計コンペで受注しました。"},
        {"source": "Rising sea levels threaten to submerge island nations within fifty years.", "reference": "海面上昇は50年以内に島嶼国を水没させる恐れがあります。"},
        {"source": "The airline introduced a direct route connecting two major business hubs.", "reference": "航空会社が二大ビジネス拠点を結ぶ直行便を新設しました。"},
        {"source": "Critics praised the novel for its portrayal of generational trauma.", "reference": "批評家たちは世代的トラウマの描写でその小説を絶賛しました。"},
        {"source": "World leaders produced a joint declaration on nuclear disarmament.", "reference": "世界の指導者たちが核軍縮に関する共同宣言を発表しました。"},
        {"source": "Biologists mapped the genome of an unknown organism from the ocean floor.", "reference": "生物学者たちが海底で発見された未知の生物のゲノムを解読しました。"},
        {"source": "The retail sector reported its weakest quarterly performance in a decade.", "reference": "小売部門は10年ぶりとなる最低の四半期業績を報告しました。"},
        {"source": "Teachers are calling for smaller class sizes to improve outcomes.", "reference": "教師たちは学習成果向上のためにクラスの人数削減を求めています。"},
        {"source": "The opposition secured enough seats in parliament to form a minority government.", "reference": "野党が少数与党を組む十分な議席を獲得しました。"},
        {"source": "A new report highlights gender pay gaps in technology and finance.", "reference": "新しい報告書がテクノロジーと金融分野における男女間の賃金格差を指摘しています。"},
        {"source": "The ancient manuscript was digitized and made available online.", "reference": "古代の写本がデジタル化され、オンラインで公開されました。"},
        {"source": "Manufacturers face semiconductor shortages due to supply chain disruptions.", "reference": "メーカーはサプライチェーンの混乱による半導体不足に直面しています。"},
        {"source": "The cycling team completed the mountain stage in record time.", "reference": "サイクリングチームが山岳ステージを記録的な時間で完走しました。"},
        {"source": "Data privacy advocates push for stricter regulations on personal data collection.", "reference": "データプライバシー擁護者たちが個人情報収集に関するより厳格な規制を求めています。"},
        {"source": "The conservation project reintroduced wolves to the national park.", "reference": "保全プロジェクトが国立公園にオオカミを再導入しました。"},
        {"source": "The finance minister presented the annual budget amid public debt concerns.", "reference": "財務大臣が公的債務への懸念が高まる中、年次予算を発表しました。"},
        {"source": "Authorities issued a public health advisory following a respiratory illness outbreak.", "reference": "当局が呼吸器疾患の発生を受けて公衆衛生に関する勧告を出しました。"},
        {"source": "The solar power plant will supply electricity to one hundred thousand homes.", "reference": "その太陽光発電所は10万世帯に電力を供給します。"},
        {"source": "Rehabilitation programs reduce recidivism more effectively than harsher sentences.", "reference": "更生プログラムはより厳しい刑罰よりも効果的に再犯を減少させます。"},
        {"source": "The foreign minister discussed bilateral trade and security with her counterpart.", "reference": "外務大臣は相手国の外相と二国間貿易および安全保障について協議しました。"},
        {"source": "The smartphone manufacturer unveiled its latest flagship with an improved camera.", "reference": "スマートフォンメーカーがカメラ性能を向上させた最新フラッグシップ機を発表しました。"},
        {"source": "A landslide buried several homes after days of heavy rainfall.", "reference": "数日間の豪雨の後、地滑りが数軒の家を埋め尽くしました。"},
        {"source": "The central bank intervened to stabilize the depreciating exchange rate.", "reference": "中央銀行が下落する為替レートを安定させるために介入しました。"},
        {"source": "Genetic research shed light on early human migration patterns.", "reference": "遺伝学的研究が初期の人類の移動パターンに新たな光を当てました。"},
        {"source": "The housing shortage has driven up rents and displaced low-income families.", "reference": "住宅不足により家賃が上昇し、低所得世帯が住居を失っています。"},
        {"source": "International observers declared the election results credible.", "reference": "国際監視員たちが選挙結果の信頼性を確認しました。"},
    ],

    "jp-en": [
        {"source": "猫がマットの上に座っています。", "reference": "The cat sits on the mat."},
        {"source": "こんにちは、元気ですか？", "reference": "Hello, how are you?"},
        {"source": "機械翻訳が向上しています。", "reference": "Machine translation is improving."},
        {"source": "今日はいい天気です。", "reference": "The weather is nice today."},
        {"source": "コーヒーを注文したいです。", "reference": "I would like to order coffee."},
        {"source": "科学者たちが新種の深海魚を発見しました。", "reference": "Scientists have discovered a new species of deep-sea fish."},
        {"source": "政府は失業率を下げるための経済改革を発表しました。", "reference": "The government announced economic reforms to reduce unemployment."},
        {"source": "再生可能エネルギーがより手頃になってきています。", "reference": "Renewable energy is becoming more affordable."},
        {"source": "病院は救急室の待ち時間が短縮されたと報告しました。", "reference": "The hospital reported shorter emergency room wait times."},
        {"source": "定期的に読書する子供たちはより豊かな語彙を身につけます。", "reference": "Children who read regularly develop stronger vocabulary."},
        {"source": "新しい交通路線が市内中心部と空港を結ぶ予定です。", "reference": "The new transit line will connect downtown to the airport."},
        {"source": "研究者たちが海藻から生分解性プラスチックの代替品を開発しました。", "reference": "Researchers developed a biodegradable plastic alternative from seaweed."},
        {"source": "首相は難民問題に関する国際協力を求めました。", "reference": "The prime minister called for international cooperation on refugees."},
        {"source": "地元の農家は水を節約するために精密農業を活用しています。", "reference": "Local farmers are using precision agriculture to save water."},
        {"source": "美術館の展覧会では技術と現代アートの交差点を探求しています。", "reference": "The museum exhibition explores technology and contemporary art."},
        {"source": "地震が太平洋全域に津波警報を引き起こしました。", "reference": "An earthquake triggered tsunami warnings across the Pacific."},
        {"source": "中央銀行はインフレに対抗するために金利を引き上げました。", "reference": "The central bank raised interest rates to combat inflation."},
        {"source": "電気自動車の販売台数が初めて内燃機関車を上回りました。", "reference": "Electric vehicle sales surpassed combustion engine cars for the first time."},
        {"source": "同社は世界の従業員の15パーセントを解雇する予定です。", "reference": "The company will lay off fifteen percent of its global workforce."},
        {"source": "天文学者たちが生命居住可能な可能性のある系外惑星を検出しました。", "reference": "Astronomers detected a potentially habitable exoplanet."},
        {"source": "新しい薬がアルツハイマー病の治療に有望な結果を示しました。", "reference": "The new drug showed promising results for Alzheimer's treatment."},
        {"source": "都市計画家たちは歩行者を優先するために都市を再設計しています。", "reference": "Urban planners are redesigning cities to prioritize pedestrians."},
        {"source": "その映画は国際映画祭で最高賞を受賞しました。", "reference": "The film won the top prize at the international film festival."},
        {"source": "保健当局はインフルエンザシーズン前に住民にワクチン接種を促しました。", "reference": "Health authorities urged residents to get vaccinated before flu season."},
        {"source": "国境問題での意見の相違から条約交渉が決裂しました。", "reference": "Treaty negotiations collapsed over disagreements on territorial boundaries."},
        {"source": "ソフトウェア開発者はコードレビューを高速化するために人工知能を活用しています。", "reference": "Software developers use artificial intelligence to speed up code review."},
        {"source": "干ばつが南部地域の農作物の収穫量に深刻な影響を与えました。", "reference": "The drought severely affected crop yields in the southern region."},
        {"source": "環境団体が石油化学工場に対して訴訟を起こしました。", "reference": "Environmental groups filed a lawsuit against the petrochemical plant."},
        {"source": "野党指導者が汚職の罪で逮捕されました。", "reference": "The opposition leader was arrested on corruption charges."},
        {"source": "外科医たちが世界初の完全ロボット心臓移植手術を行いました。", "reference": "Surgeons performed the world's first fully robotic heart transplant."},
        {"source": "中央図書館はデジタルメディアセンターを含む形に改装されます。", "reference": "The central library will be renovated to include a digital media center."},
        {"source": "インフレが40年ぶりの最高水準に達しました。", "reference": "Inflation reached its highest level in four decades."},
        {"source": "国内サッカーチームがワールドカップ出場権を獲得しました。", "reference": "The national football team qualified for the World Cup."},
        {"source": "定期的な運動は認知症のリスクを軽減できます。", "reference": "Regular physical activity can reduce the risk of dementia."},
        {"source": "そのスタートアップは5000万ドルのベンチャーキャピタル資金を調達しました。", "reference": "The startup secured fifty million dollars in venture capital funding."},
        {"source": "山火事が50万ヘクタール以上の森林を焼き尽くしました。", "reference": "Wildfires consumed more than half a million hectares of forest."},
        {"source": "考古学的発掘調査で3000年前の遺物が発見されました。", "reference": "The archaeological excavation uncovered three-thousand-year-old artifacts."},
        {"source": "遅延した便の乗客は航空会社からホテルの宿泊を提供されました。", "reference": "Passengers on the delayed flight received hotel accommodation from the airline."},
        {"source": "新しい教育政策では7歳からコーディングの授業が必修となります。", "reference": "The new education policy requires coding classes from age seven."},
        {"source": "昨年、過去最多の観光客が訪れました。", "reference": "A record number of tourists visited the country last year."},
        {"source": "裁判官は証拠不十分を理由に訴訟を却下しました。", "reference": "The judge dismissed the case due to insufficient evidence."},
        {"source": "海洋酸性化はサンゴ礁の生態系に深刻な脅威をもたらしています。", "reference": "Ocean acidification poses a serious threat to coral reef ecosystems."},
        {"source": "その著者の小説は多文化社会におけるアイデンティティを探求しています。", "reference": "The author's novel explores identity in a multicultural society."},
        {"source": "知的財産権をめぐる対立から貿易協定交渉が行き詰まりました。", "reference": "Trade agreement negotiations stalled over intellectual property rights."},
        {"source": "その慈善団体は災害救援のために200万ユーロを集めました。", "reference": "The charity raised two million euros for disaster relief."},
        {"source": "衛星画像により北極の氷床が縮小していることが確認されました。", "reference": "Satellite imagery confirms the polar ice cap has shrunk."},
        {"source": "市議会が新しい低価格住宅開発を承認しました。", "reference": "The city council approved a new affordable housing development."},
        {"source": "量子コンピューティングは10年以内に創薬に革命をもたらすでしょう。", "reference": "Quantum computing will revolutionize drug discovery within a decade."},
        {"source": "抗議行進には気候変動対策を求める数万人が参加しました。", "reference": "The protest march drew tens of thousands calling for climate action."},
        {"source": "当局が不正行為に関する調査を開始しました。", "reference": "Authorities launched an investigation into financial misconduct."},
        {"source": "その難民キャンプは現在3万人を収容しています。", "reference": "The refugee camp now shelters thirty thousand people."},
        {"source": "過度なスクリーンタイムは10代の不安やうつ病と関連しています。", "reference": "Excessive screen time is linked to anxiety and depression in teenagers."},
        {"source": "オーケストラは満員の観衆の前でベートーヴェンの第9番を演奏しました。", "reference": "The orchestra performed Beethoven's Ninth to a sold-out crowd."},
        {"source": "国境警備員が偽造医薬品の積荷を押収しました。", "reference": "Border officials intercepted counterfeit pharmaceutical shipments."},
        {"source": "通信会社の合併は複数の国での規制当局の承認が必要です。", "reference": "The telecom merger requires regulatory approval in multiple countries."},
        {"source": "ボランティアが川岸に1万本の木を植えました。", "reference": "Volunteers planted ten thousand trees along the riverbank."},
        {"source": "誘拐事件の容疑者が国際空港で逮捕されました。", "reference": "The kidnapping suspect was apprehended at the international airport."},
        {"source": "紛争による供給網の混乱から食料価格が急騰しました。", "reference": "Food prices surged following supply chain disruptions from the conflict."},
        {"source": "大学が人工知能倫理のセンターを設立しました。", "reference": "The university established a center for artificial intelligence ethics."},
        {"source": "両国は5年以内に関税を撤廃することで合意しました。", "reference": "The two nations agreed to eliminate trade tariffs within five years."},
        {"source": "患者は先駆的な遺伝子治療を受けた後に回復しました。", "reference": "The patient recovered after receiving pioneering gene therapy."},
        {"source": "大雪が北部の交通網を麻痺させました。", "reference": "Heavy snowfall paralyzed transport networks across the northern provinces."},
        {"source": "大手テクノロジー企業がクラウドコンピューティング企業の買収に関して独占禁止法の審査を受けています。", "reference": "The tech giant faces antitrust scrutiny over its cloud computing acquisition."},
        {"source": "地元当局はピークシーズンの観光客の急増への対応に苦慮しています。", "reference": "Local authorities are struggling to manage tourist influx during peak season."},
        {"source": "そのドキュメンタリーは紛争地帯の生活を描いたことで国際的な賞賛を得ました。", "reference": "The documentary won international acclaim for depicting life in conflict zones."},
        {"source": "エンジニアたちがカテゴリー5のハリケーンに耐えられる橋を設計しました。", "reference": "Engineers designed a bridge capable of withstanding category five hurricanes."},
        {"source": "この政策転換は数十年にわたって確立された外交政策から大きく逸脱しています。", "reference": "The policy shift departs from decades of established foreign relations doctrine."},
        {"source": "ボランティアが洪水被害を受けた町に集まり、清掃作業を支援しました。", "reference": "Volunteers converged on the flood-hit town to assist with cleanup."},
        {"source": "臨床試験では12の病院で2000人の参加者が登録されました。", "reference": "The clinical trial enrolled two thousand participants across twelve hospitals."},
        {"source": "その建築事務所が国立図書館の設計コンペで受注しました。", "reference": "The architecture firm won the contract to design the national library."},
        {"source": "海面上昇は50年以内に島嶼国を水没させる恐れがあります。", "reference": "Rising sea levels threaten to submerge island nations within fifty years."},
        {"source": "航空会社が二大ビジネス拠点を結ぶ直行便を新設しました。", "reference": "The airline introduced a direct route connecting two major business hubs."},
        {"source": "批評家たちは世代的トラウマの描写でその小説を絶賛しました。", "reference": "Critics praised the novel for its portrayal of generational trauma."},
        {"source": "世界の指導者たちが核軍縮に関する共同宣言を発表しました。", "reference": "World leaders produced a joint declaration on nuclear disarmament."},
        {"source": "生物学者たちが海底で発見された未知の生物のゲノムを解読しました。", "reference": "Biologists mapped the genome of an unknown organism from the ocean floor."},
        {"source": "小売部門は10年ぶりとなる最低の四半期業績を報告しました。", "reference": "The retail sector reported its weakest quarterly performance in a decade."},
        {"source": "教師たちは学習成果向上のためにクラスの人数削減を求めています。", "reference": "Teachers are calling for smaller class sizes to improve outcomes."},
        {"source": "野党が少数与党を組む十分な議席を獲得しました。", "reference": "The opposition secured enough seats in parliament to form a minority government."},
        {"source": "新しい報告書がテクノロジーと金融分野における男女間の賃金格差を指摘しています。", "reference": "A new report highlights gender pay gaps in technology and finance."},
        {"source": "古代の写本がデジタル化され、オンラインで公開されました。", "reference": "The ancient manuscript was digitized and made available online."},
        {"source": "メーカーはサプライチェーンの混乱による半導体不足に直面しています。", "reference": "Manufacturers face semiconductor shortages due to supply chain disruptions."},
        {"source": "サイクリングチームが山岳ステージを記録的な時間で完走しました。", "reference": "The cycling team completed the mountain stage in record time."},
        {"source": "データプライバシー擁護者たちが個人情報収集に関するより厳格な規制を求めています。", "reference": "Data privacy advocates push for stricter regulations on personal data collection."},
        {"source": "保全プロジェクトが国立公園にオオカミを再導入しました。", "reference": "The conservation project reintroduced wolves to the national park."},
        {"source": "財務大臣が公的債務への懸念が高まる中、年次予算を発表しました。", "reference": "The finance minister presented the annual budget amid public debt concerns."},
        {"source": "当局が呼吸器疾患の発生を受けて公衆衛生に関する勧告を出しました。", "reference": "Authorities issued a public health advisory following a respiratory illness outbreak."},
        {"source": "その太陽光発電所は10万世帯に電力を供給します。", "reference": "The solar power plant will supply electricity to one hundred thousand homes."},
        {"source": "更生プログラムはより厳しい刑罰よりも効果的に再犯を減少させます。", "reference": "Rehabilitation programs reduce recidivism more effectively than harsher sentences."},
        {"source": "外務大臣は相手国の外相と二国間貿易および安全保障について協議しました。", "reference": "The foreign minister discussed bilateral trade and security with her counterpart."},
        {"source": "スマートフォンメーカーがカメラ性能を向上させた最新フラッグシップ機を発表しました。", "reference": "The smartphone manufacturer unveiled its latest flagship with an improved camera."},
        {"source": "数日間の豪雨の後、地滑りが数軒の家を埋め尽くしました。", "reference": "A landslide buried several homes after days of heavy rainfall."},
        {"source": "中央銀行が下落する為替レートを安定させるために介入しました。", "reference": "The central bank intervened to stabilize the depreciating exchange rate."},
        {"source": "遺伝学的研究が初期の人類の移動パターンに新たな光を当てました。", "reference": "Genetic research shed light on early human migration patterns."},
        {"source": "住宅不足により家賃が上昇し、低所得世帯が住居を失っています。", "reference": "The housing shortage has driven up rents and displaced low-income families."},
        {"source": "国際監視員たちが選挙結果の信頼性を確認しました。", "reference": "International observers declared the election results credible."},
    ],

    "en-sw": [
        {"source": "On Monday, scientists from the Stanford University School of Medicine announced the invention of a new diagnostic tool that can sort cells by type.", "reference": "Siku ya Jumatatu, wanasayansi kutoka Shule ya Tiba ya Chuo Kikuu cha Stanford walitangaza uvumbuzi wa chombo kipya cha uchunguzi ambacho kinaweza kupanga seli kwa aina."},
        {"source": "The device can distinguish cancer cells from healthy cells, and researchers hope it can be used to detect disease earlier.", "reference": "Kifaa hicho kinaweza kutofautisha seli za saratani kutoka kwa seli zenye afya, na watafiti wana matumaini kwamba kinaweza kutumika kugundua ugonjwa mapema zaidi."},
        {"source": "A miniature version of the tool was built using a 3D printer.", "reference": "Toleo dogo la chombo hicho lilijengwa kwa kutumia kichapishi cha 3D."},
        {"source": "The researchers say this technology could help fight malaria, HIV and tuberculosis.", "reference": "Watafiti wanasema teknolojia hii inaweza kusaidia kupigana na malaria, VVU na kifua kikuu."},
        {"source": "The study was published in the journal Proceedings of the National Academy of Sciences.", "reference": "Utafiti huo ulichapishwa katika jarida la Proceedings of the National Academy of Sciences."},
        {"source": "California is a state in the western United States and is the most populous state in the country.", "reference": "California ni jimbo la magharibi mwa Marekani na ndilo jimbo lenye watu wengi zaidi nchini."},
        {"source": "The weather in San Francisco is mild due to its proximity to the ocean.", "reference": "Hali ya hewa huko San Francisco ni ya wastani kwa sababu ya ukaribu wake na bahari."},
        {"source": "Education plays a crucial role in the development of any society.", "reference": "Elimu inacheza jukumu muhimu katika maendeleo ya jamii yoyote."},
        {"source": "The committee met to discuss the proposed changes to the healthcare system.", "reference": "Kamati ilikutana kujadili mabadiliko yaliyopendekezwa kwa mfumo wa huduma za afya."},
        {"source": "Water scarcity is becoming an increasingly urgent problem in many parts of the world.", "reference": "Ukosefu wa maji unakuwa tatizo la dharura zaidi katika sehemu nyingi za ulimwengu."},
        {"source": "The government announced new measures to support small and medium-sized businesses.", "reference": "Serikali ilitangaza hatua mpya za kusaidia biashara ndogo na za kati."},
        {"source": "Thousands of people were displaced following the flooding in the coastal regions.", "reference": "Maelfu ya watu walihama makwao baada ya mafuriko katika maeneo ya pwani."},
        {"source": "The parliament passed a new law requiring all vehicles to undergo annual safety inspections.", "reference": "Bunge lilipitisha sheria mpya inayohitaji magari yote kufanyiwa ukaguzi wa usalama kila mwaka."},
        {"source": "Doctors without Borders established a new clinic in the remote village to provide medical care.", "reference": "Madaktari bila Mipaka walianzisha kliniki mpya katika kijiji cha mbali kutoa huduma za matibabu."},
        {"source": "The United Nations called for an immediate ceasefire to allow humanitarian aid to reach the affected population.", "reference": "Umoja wa Mataifa uliitaka kusimamishwa mara moja kwa mapigano ili kuruhusu msaada wa kibinadamu kufikia wakazi walioathirika."},
        {"source": "Mobile phone usage has increased dramatically across sub-Saharan Africa over the past decade.", "reference": "Matumizi ya simu za mkononi yameongezeka kwa kasi sana Afrika Kusini mwa Jangwa la Sahara katika muongo uliopita."},
        {"source": "The construction of the new highway will significantly reduce travel time between the two cities.", "reference": "Ujenzi wa barabara kuu mpya utapunguza kwa kiasi kikubwa muda wa safari kati ya miji miwili."},
        {"source": "Agricultural production has declined due to irregular rainfall patterns caused by climate change.", "reference": "Uzalishaji wa kilimo umepungua kutokana na mifumo ya mvua isiyo ya kawaida iliyosababishwa na mabadiliko ya tabianchi."},
        {"source": "The new hospital will serve a population of over one million people in the surrounding region.", "reference": "Hospitali mpya itahudumia idadi ya watu zaidi ya milioni moja katika eneo la jirani."},
        {"source": "Researchers have developed a new vaccine that could protect against multiple strains of malaria.", "reference": "Watafiti wametengeneza chanjo mpya ambayo inaweza kulinda dhidi ya aina nyingi za malaria."},
        {"source": "The president signed a trade agreement with neighboring countries to boost regional economic cooperation.", "reference": "Rais alitia saini makubaliano ya biashara na nchi jirani ili kukuza ushirikiano wa kiuchumi wa kikanda."},
        {"source": "Access to clean drinking water remains a major challenge for millions of people in rural areas.", "reference": "Upatikanaji wa maji safi ya kunywa bado ni changamoto kubwa kwa mamilioni ya watu katika maeneo ya vijijini."},
        {"source": "The school feeding program has improved student attendance and academic performance significantly.", "reference": "Mpango wa chakula shuleni umeboresha mahudhurio ya wanafunzi na utendaji wa kitaaluma kwa kiasi kikubwa."},
        {"source": "Scientists warn that deforestation is accelerating the loss of biodiversity in tropical forests.", "reference": "Wanasayansi wanaonya kwamba ukataji miti unakuza upotezaji wa bioanuwai katika misitu ya kitropiki."},
        {"source": "The government launched a new initiative to provide affordable housing to low-income families.", "reference": "Serikali ilianzisha mpango mpya wa kutoa nyumba za bei nafuu kwa familia zenye kipato kidogo."},
        {"source": "Local communities are working together to protect their natural resources from exploitation.", "reference": "Jamii za mtaa zinashirikiana kulinda rasilimali zao za asili dhidi ya unyonyaji."},
        {"source": "The fishing industry provides livelihoods for millions of families living along the coastline.", "reference": "Sekta ya uvuvi inatoa riziki kwa mamilioni ya familia zinazokaa kando ya pwani."},
        {"source": "New solar energy installations are bringing electricity to remote villages for the first time.", "reference": "Vifaa vipya vya nishati ya jua vinaleta umeme katika vijiji vya mbali kwa mara ya kwanza."},
        {"source": "The outbreak of the disease has overwhelmed the local health system and called for international assistance.", "reference": "Mlipuko wa ugonjwa huo umezidisha mfumo wa afya wa mtaa na kuomba msaada wa kimataifa."},
        {"source": "Youth unemployment remains one of the greatest challenges facing the continent.", "reference": "Ukosefu wa ajira kwa vijana bado ni moja ya changamoto kubwa zaidi zinazokabili bara hilo."},
        {"source": "The construction of new schools in rural areas is part of the government's education expansion plan.", "reference": "Ujenzi wa shule mpya katika maeneo ya vijijini ni sehemu ya mpango wa serikali wa kupanua elimu."},
        {"source": "Conservation efforts have helped increase the population of endangered wildlife species.", "reference": "Juhudi za uhifadhi zimesaidia kuongeza idadi ya spishi za wanyamapori walio hatarini kutoweka."},
        {"source": "The annual harvest festival brings together communities from across the region to celebrate.", "reference": "Sherehe ya kuvuna kila mwaka huleta pamoja jamii kutoka katika mkoa mzima kusherehekea."},
        {"source": "Improved road infrastructure is connecting remote communities to markets and essential services.", "reference": "Miundombinu bora ya barabara inaunganisha jamii za mbali na masoko na huduma muhimu."},
        {"source": "The new curriculum includes lessons on environmental conservation and sustainable development.", "reference": "Mtaala mpya unajumuisha masomo kuhusu uhifadhi wa mazingira na maendeleo endelevu."},
        {"source": "Women's participation in political leadership has increased significantly over the past two decades.", "reference": "Ushiriki wa wanawake katika uongozi wa kisiasa umeongezeka kwa kiasi kikubwa katika miongo miwili iliyopita."},
        {"source": "The microfinance program has enabled thousands of women to start their own small businesses.", "reference": "Mpango wa fedha ndogo ndogo umesaidia maelfu ya wanawake kuanzisha biashara zao ndogo."},
        {"source": "Drought conditions have forced many families to abandon their farms and migrate to urban areas.", "reference": "Hali ya ukame imewalazimisha familia nyingi kuacha mashamba yao na kuhama kwenda maeneo ya mijini."},
        {"source": "The coastal erosion caused by rising sea levels is threatening fishing communities along the shore.", "reference": "Mmomonyoko wa pwani unaosababishwa na kupanda kwa kina cha bahari unawatishia jamii za wavuvi pwani."},
        {"source": "Traditional medicine continues to play an important role alongside modern healthcare in many communities.", "reference": "Dawa ya jadi inaendelea kucheza jukumu muhimu pamoja na huduma za afya za kisasa katika jamii nyingi."},
        {"source": "The peacekeeping mission has helped restore stability to the conflict-affected region.", "reference": "Dhamira ya kulinda amani imesaidia kurejesha utulivu katika eneo lililoathiriwa na migogoro."},
        {"source": "Improved access to maternal healthcare has significantly reduced infant and maternal mortality rates.", "reference": "Uboreshaji wa upatikanaji wa huduma za afya ya uzazi umepunguza kwa kiasi kikubwa viwango vya vifo vya watoto wachanga na mama."},
        {"source": "The national parks attract thousands of international tourists each year, generating vital revenue.", "reference": "Mbuga za taifa huvutia maelfu ya watalii wa kimataifa kila mwaka, zikizalisha mapato muhimu."},
        {"source": "Rapid urbanization is creating new challenges for city planners and local governments.", "reference": "Ukuaji wa haraka wa miji unaweka changamoto mpya kwa wapangaji wa miji na serikali za mtaa."},
        {"source": "The introduction of mobile banking services has transformed financial access in rural communities.", "reference": "Utangulizi wa huduma za benki za simu umebadilisha upatikanaji wa huduma za fedha katika jamii za vijijini."},
        {"source": "Improved sanitation facilities are helping to prevent the spread of waterborne diseases.", "reference": "Vifaa bora vya usafi wa mazingira vinasaidia kuzuia kuenea kwa magonjwa yanayotokana na maji."},
        {"source": "The literacy campaign has helped millions of adults learn to read and write.", "reference": "Kampeni ya kusoma na kuandika imesaidia mamilioni ya watu wazima kujifunza kusoma na kuandika."},
        {"source": "Community health workers are essential to extending healthcare services to underserved populations.", "reference": "Wafanyakazi wa afya wa jamii ni muhimu katika kupanua huduma za afya kwa watu wasiohudumika."},
        {"source": "The expansion of internet connectivity is opening new economic opportunities for young entrepreneurs.", "reference": "Upanuzi wa muunganisho wa intaneti unafungua fursa mpya za kiuchumi kwa wajasiriamali vijana."},
        {"source": "Sustainable tourism initiatives are helping protect natural ecosystems while supporting local economies.", "reference": "Mipango ya utalii endelevu inasaidia kulinda mifumo ikolojia ya asili huku ikisaidia uchumi wa mtaa."},
        {"source": "The construction of irrigation canals has transformed arid land into productive agricultural zones.", "reference": "Ujenzi wa mifereji ya umwagiliaji umebadilisha ardhi kame kuwa maeneo yenye tija ya kilimo."},
        {"source": "Regional cooperation agreements are strengthening trade and cultural ties between neighboring nations.", "reference": "Makubaliano ya ushirikiano wa kikanda yanaimarisha uhusiano wa biashara na utamaduni kati ya mataifa jirani."},
        {"source": "The discovery of offshore oil reserves has the potential to transform the country's economy.", "reference": "Ugunduzi wa akiba ya mafuta ya baharini una uwezo wa kubadilisha uchumi wa nchi."},
        {"source": "Efforts to combat illegal wildlife trafficking are gaining momentum across the region.", "reference": "Juhudi za kupambana na usafirishaji haramu wa wanyamapori zinapata nguvu katika mkoa mzima."},
        {"source": "The introduction of e-government services has made it easier for citizens to access public administration.", "reference": "Utangulizi wa huduma za serikali ya kielektroniki umefanya iwe rahisi kwa raia kupata utawala wa umma."},
        {"source": "Climate-smart agriculture techniques are helping farmers adapt to changing weather patterns.", "reference": "Mbinu za kilimo zinazozingatia hali ya hewa zinawasaidia wakulima kukabiliana na mabadiliko ya hali ya hewa."},
        {"source": "The new bridge over the river will facilitate trade and movement between the two regions.", "reference": "Daraja jipya juu ya mto litawezesha biashara na harakati kati ya maeneo mawili."},
        {"source": "Investment in early childhood education produces significant long-term social and economic benefits.", "reference": "Uwekezaji katika elimu ya awali ya utotoni unazalisha faida kubwa za kijamii na kiuchumi za muda mrefu."},
        {"source": "The peace talks aim to resolve the decades-long territorial dispute between the two nations.", "reference": "Mazungumzo ya amani yanalenga kutatua mgogoro wa eneo uliodumu kwa miongo mingi kati ya mataifa mawili."},
        {"source": "Remittances from the diaspora represent a significant source of income for many families.", "reference": "Fedha zinazotumwa na diaspora zinawakilisha chanzo kikubwa cha mapato kwa familia nyingi."},
        {"source": "The proliferation of smartphones has transformed how people access news and information.", "reference": "Kuenea kwa simu mahiri kumebadilisha jinsi watu wanavyopata habari na taarifa."},
        {"source": "Urban farming initiatives are helping address food security challenges in densely populated cities.", "reference": "Mipango ya kilimo cha mijini inasaidia kushughulikia changamoto za usalama wa chakula katika miji yenye watu wengi."},
        {"source": "The restoration of mangrove forests along the coast is helping protect against storm surges.", "reference": "Urejeshaji wa misitu ya mikoko pwani unasaidia kulinda dhidi ya mawimbi ya dhoruba."},
        {"source": "International aid organizations are working to improve nutrition outcomes for malnourished children.", "reference": "Mashirika ya msaada wa kimataifa yanafanya kazi kuboresha matokeo ya lishe kwa watoto wenye utapiamlo."},
        {"source": "The new railway line will reduce transportation costs and boost trade across the region.", "reference": "Njia mpya ya reli itapunguza gharama za usafirishaji na kukuza biashara katika mkoa mzima."},
        {"source": "Women entrepreneurs are driving economic growth in many underserved communities across the continent.", "reference": "Wajasiriamali wanawake wanaendesha ukuaji wa uchumi katika jamii nyingi zisizohudumika vizuri barani."},
        {"source": "The government has pledged to increase investment in vocational training programs to reduce youth unemployment.", "reference": "Serikali imeahidi kuongeza uwekezaji katika mipango ya mafunzo ya ufundi ili kupunguza ukosefu wa ajira kwa vijana."},
        {"source": "Traditional cultural practices are being preserved through community-led heritage programs.", "reference": "Desturi za kitamaduni zinahifadhiwa kupitia mipango ya urithi inayoongozwa na jamii."},
        {"source": "The development of geothermal energy resources could provide sustainable power to millions of homes.", "reference": "Maendeleo ya rasilimali za nishati ya jotoardhi yanaweza kutoa nguvu endelevu kwa mamilioni ya nyumba."},
        {"source": "Border security has been strengthened to prevent the smuggling of weapons and contraband.", "reference": "Usalama wa mipaka umeimarishwa ili kuzuia usafirishaji haramu wa silaha na bidhaa haramu."},
        {"source": "The annual report shows significant progress in reducing child mortality rates across the region.", "reference": "Ripoti ya kila mwaka inaonyesha maendeleo makubwa katika kupunguza viwango vya vifo vya watoto katika mkoa."},
        {"source": "Advances in mobile health technology are bringing diagnostic services to remote communities.", "reference": "Maendeleo katika teknolojia ya afya ya simu yanaleta huduma za uchunguzi kwa jamii za mbali."},
        {"source": "The ratification of the climate agreement marks an important step in the country's environmental commitments.", "reference": "Uridhishaji wa makubaliano ya hali ya hewa unaashiria hatua muhimu katika ahadi za mazingira za nchi."},
        {"source": "Community-based organizations are playing a vital role in distributing food aid to vulnerable populations.", "reference": "Mashirika yanayotegemea jamii yanacheza jukumu muhimu katika kusambaza msaada wa chakula kwa watu walio hatarini."},
        {"source": "The expansion of the port will increase the country's capacity to handle international trade.", "reference": "Upanuzi wa bandari utaongeza uwezo wa nchi wa kushughulikia biashara ya kimataifa."},
        {"source": "Efforts to promote girls' education are showing measurable results in closing the gender gap.", "reference": "Juhudi za kukuza elimu ya wasichana zinaonyesha matokeo yanayoweza kupimika katika kufunga pengo la kijinsia."},
        {"source": "The introduction of community health insurance schemes has improved healthcare access for rural populations.", "reference": "Utangulizi wa mipango ya bima ya afya ya jamii umeboresha upatikanaji wa huduma za afya kwa watu wa vijijini."},
        {"source": "Scientists are studying the impact of microplastic pollution on marine ecosystems.", "reference": "Wanasayansi wanastudia athari za uchafuzi wa plastiki ndogo ndogo kwenye mifumo ikolojia ya baharini."},
        {"source": "The digital skills training program has helped thousands of young people find employment in the technology sector.", "reference": "Mpango wa mafunzo ya ujuzi wa kidijitali umesaidia vijana maelfu kupata ajira katika sekta ya teknolojia."},
        {"source": "Regional food banks are working to address hunger and food insecurity among vulnerable households.", "reference": "Benki za chakula za kikanda zinafanya kazi kushughulikia njaa na ukosefu wa usalama wa chakula miongoni mwa kaya zilizo hatarini."},
        {"source": "The construction of new health centers in underserved areas will bring medical care closer to communities.", "reference": "Ujenzi wa vituo vipya vya afya katika maeneo yasiyohudumika vizuri utawaletea huduma za matibabu jamii karibu zaidi."},
        {"source": "Improved weather forecasting systems are helping farmers plan their planting and harvesting seasons.", "reference": "Mifumo iliyoboreshwa ya utabiri wa hali ya hewa inawasaidia wakulima kupanga misimu yao ya kupanda na kuvuna."},
        {"source": "The discovery of a new underground water source could transform water access for surrounding communities.", "reference": "Ugunduzi wa chanzo kipya cha maji chini ya ardhi unaweza kubadilisha upatikanaji wa maji kwa jamii zinazozunguka."},
        {"source": "The international community has pledged significant financial support for the reconstruction effort.", "reference": "Jumuiya ya kimataifa imeahidi msaada mkubwa wa fedha kwa juhudi za ujenzi upya."},
        {"source": "Local entrepreneurs are leveraging digital platforms to reach customers beyond their immediate communities.", "reference": "Wajasiriamali wa mtaa wanatumia majukwaa ya kidijitali kufikia wateja zaidi ya jamii zao za karibu."},
        {"source": "The new nature reserve will protect one of the last remaining habitats of the endangered primate species.", "reference": "Hifadhi mpya ya asili itawalinda moja ya makazi ya mwisho yaliyobaki ya spishi ya nyani walio hatarini."},
        {"source": "Increased investment in renewable energy infrastructure will reduce dependence on imported fossil fuels.", "reference": "Uwekezaji ulioongezeka katika miundombinu ya nishati mbadala utapunguza utegemezi wa mafuta ya kisukuku yanayoagizwa kutoka nje."},
        {"source": "The community radio station broadcasts health information and agricultural tips to rural audiences.", "reference": "Kituo cha redio cha jamii kinatangaza taarifa za afya na vidokezo vya kilimo kwa hadhira ya vijijini."},
        {"source": "Partnerships between universities and industry are producing graduates with skills relevant to the modern economy.", "reference": "Ushirikiano kati ya vyuo vikuu na sekta ya viwanda unazalisha wahitimu wenye ujuzi unaohusiana na uchumi wa kisasa."},
        {"source": "The annual migration of wildebeest across the plains attracts tourists from around the world.", "reference": "Uhamiaji wa kila mwaka wa nyumbu katika tambarare huvutia watalii kutoka kote duniani."},
        {"source": "The government has invested in upgrading roads to connect rural farming communities to urban markets.", "reference": "Serikali imewekeza katika kuboresha barabara ili kuunganisha jamii za wakulima wa vijijini na masoko ya mijini."},
        {"source": "Access to justice remains limited for many low-income citizens due to high legal costs.", "reference": "Upatikanaji wa haki bado ni mdogo kwa raia wengi wa kipato kidogo kutokana na gharama kubwa za kisheria."},
        {"source": "Efforts to improve air quality in major cities are being driven by new environmental regulations.", "reference": "Juhudi za kuboresha ubora wa hewa katika miji mikubwa zinaendelezwa na kanuni mpya za mazingira."},
        {"source": "The new water treatment plant will provide clean drinking water to more than half a million residents.", "reference": "Kiwanda kipya cha matibabu ya maji kitatoa maji safi ya kunywa kwa wakazi zaidi ya nusu milioni."},
        {"source": "Youth leadership programs are empowering the next generation to participate in civic and political life.", "reference": "Mipango ya uongozi wa vijana inaweza nguvu kizazi kijacho kushiriki katika maisha ya kiraia na kisiasa."},
    ],

    "sw-en": [
        {"source": "Siku ya Jumatatu, wanasayansi kutoka Shule ya Tiba ya Chuo Kikuu cha Stanford walitangaza uvumbuzi wa chombo kipya cha uchunguzi ambacho kinaweza kupanga seli kwa aina.", "reference": "On Monday, scientists from the Stanford University School of Medicine announced the invention of a new diagnostic tool that can sort cells by type."},
        {"source": "Kifaa hicho kinaweza kutofautisha seli za saratani kutoka kwa seli zenye afya, na watafiti wana matumaini kwamba kinaweza kutumika kugundua ugonjwa mapema zaidi.", "reference": "The device can distinguish cancer cells from healthy cells, and researchers hope it can be used to detect disease earlier."},
        {"source": "Toleo dogo la chombo hicho lilijengwa kwa kutumia kichapishi cha 3D.", "reference": "A miniature version of the tool was built using a 3D printer."},
        {"source": "Watafiti wanasema teknolojia hii inaweza kusaidia kupigana na malaria, VVU na kifua kikuu.", "reference": "The researchers say this technology could help fight malaria, HIV and tuberculosis."},
        {"source": "Utafiti huo ulichapishwa katika jarida la Proceedings of the National Academy of Sciences.", "reference": "The study was published in the journal Proceedings of the National Academy of Sciences."},
        {"source": "California ni jimbo la magharibi mwa Marekani na ndilo jimbo lenye watu wengi zaidi nchini.", "reference": "California is a state in the western United States and is the most populous state in the country."},
        {"source": "Hali ya hewa huko San Francisco ni ya wastani kwa sababu ya ukaribu wake na bahari.", "reference": "The weather in San Francisco is mild due to its proximity to the ocean."},
        {"source": "Elimu inacheza jukumu muhimu katika maendeleo ya jamii yoyote.", "reference": "Education plays a crucial role in the development of any society."},
        {"source": "Kamati ilikutana kujadili mabadiliko yaliyopendekezwa kwa mfumo wa huduma za afya.", "reference": "The committee met to discuss the proposed changes to the healthcare system."},
        {"source": "Ukosefu wa maji unakuwa tatizo la dharura zaidi katika sehemu nyingi za ulimwengu.", "reference": "Water scarcity is becoming an increasingly urgent problem in many parts of the world."},
        {"source": "Serikali ilitangaza hatua mpya za kusaidia biashara ndogo na za kati.", "reference": "The government announced new measures to support small and medium-sized businesses."},
        {"source": "Maelfu ya watu walihama makwao baada ya mafuriko katika maeneo ya pwani.", "reference": "Thousands of people were displaced following the flooding in the coastal regions."},
        {"source": "Bunge lilipitisha sheria mpya inayohitaji magari yote kufanyiwa ukaguzi wa usalama kila mwaka.", "reference": "The parliament passed a new law requiring all vehicles to undergo annual safety inspections."},
        {"source": "Madaktari bila Mipaka walianzisha kliniki mpya katika kijiji cha mbali kutoa huduma za matibabu.", "reference": "Doctors without Borders established a new clinic in the remote village to provide medical care."},
        {"source": "Umoja wa Mataifa uliitaka kusimamishwa mara moja kwa mapigano ili kuruhusu msaada wa kibinadamu kufikia wakazi walioathirika.", "reference": "The United Nations called for an immediate ceasefire to allow humanitarian aid to reach the affected population."},
        {"source": "Matumizi ya simu za mkononi yameongezeka kwa kasi sana Afrika Kusini mwa Jangwa la Sahara katika muongo uliopita.", "reference": "Mobile phone usage has increased dramatically across sub-Saharan Africa over the past decade."},
        {"source": "Ujenzi wa barabara kuu mpya utapunguza kwa kiasi kikubwa muda wa safari kati ya miji miwili.", "reference": "The construction of the new highway will significantly reduce travel time between the two cities."},
        {"source": "Uzalishaji wa kilimo umepungua kutokana na mifumo ya mvua isiyo ya kawaida iliyosababishwa na mabadiliko ya tabianchi.", "reference": "Agricultural production has declined due to irregular rainfall patterns caused by climate change."},
        {"source": "Hospitali mpya itahudumia idadi ya watu zaidi ya milioni moja katika eneo la jirani.", "reference": "The new hospital will serve a population of over one million people in the surrounding region."},
        {"source": "Watafiti wametengeneza chanjo mpya ambayo inaweza kulinda dhidi ya aina nyingi za malaria.", "reference": "Researchers have developed a new vaccine that could protect against multiple strains of malaria."},
        {"source": "Rais alitia saini makubaliano ya biashara na nchi jirani ili kukuza ushirikiano wa kiuchumi wa kikanda.", "reference": "The president signed a trade agreement with neighboring countries to boost regional economic cooperation."},
        {"source": "Upatikanaji wa maji safi ya kunywa bado ni changamoto kubwa kwa mamilioni ya watu katika maeneo ya vijijini.", "reference": "Access to clean drinking water remains a major challenge for millions of people in rural areas."},
        {"source": "Mpango wa chakula shuleni umeboresha mahudhurio ya wanafunzi na utendaji wa kitaaluma kwa kiasi kikubwa.", "reference": "The school feeding program has improved student attendance and academic performance significantly."},
        {"source": "Wanasayansi wanaonya kwamba ukataji miti unakuza upotezaji wa bioanuwai katika misitu ya kitropiki.", "reference": "Scientists warn that deforestation is accelerating the loss of biodiversity in tropical forests."},
        {"source": "Serikali ilianzisha mpango mpya wa kutoa nyumba za bei nafuu kwa familia zenye kipato kidogo.", "reference": "The government launched a new initiative to provide affordable housing to low-income families."},
        {"source": "Jamii za mtaa zinashirikiana kulinda rasilimali zao za asili dhidi ya unyonyaji.", "reference": "Local communities are working together to protect their natural resources from exploitation."},
        {"source": "Sekta ya uvuvi inatoa riziki kwa mamilioni ya familia zinazokaa kando ya pwani.", "reference": "The fishing industry provides livelihoods for millions of families living along the coastline."},
        {"source": "Vifaa vipya vya nishati ya jua vinaleta umeme katika vijiji vya mbali kwa mara ya kwanza.", "reference": "New solar energy installations are bringing electricity to remote villages for the first time."},
        {"source": "Mlipuko wa ugonjwa huo umezidisha mfumo wa afya wa mtaa na kuomba msaada wa kimataifa.", "reference": "The outbreak of the disease has overwhelmed the local health system and called for international assistance."},
        {"source": "Ukosefu wa ajira kwa vijana bado ni moja ya changamoto kubwa zaidi zinazokabili bara hilo.", "reference": "Youth unemployment remains one of the greatest challenges facing the continent."},
        {"source": "Ujenzi wa shule mpya katika maeneo ya vijijini ni sehemu ya mpango wa serikali wa kupanua elimu.", "reference": "The construction of new schools in rural areas is part of the government's education expansion plan."},
        {"source": "Juhudi za uhifadhi zimesaidia kuongeza idadi ya spishi za wanyamapori walio hatarini kutoweka.", "reference": "Conservation efforts have helped increase the population of endangered wildlife species."},
        {"source": "Sherehe ya kuvuna kila mwaka huleta pamoja jamii kutoka katika mkoa mzima kusherehekea.", "reference": "The annual harvest festival brings together communities from across the region to celebrate."},
        {"source": "Miundombinu bora ya barabara inaunganisha jamii za mbali na masoko na huduma muhimu.", "reference": "Improved road infrastructure is connecting remote communities to markets and essential services."},
        {"source": "Mtaala mpya unajumuisha masomo kuhusu uhifadhi wa mazingira na maendeleo endelevu.", "reference": "The new curriculum includes lessons on environmental conservation and sustainable development."},
        {"source": "Ushiriki wa wanawake katika uongozi wa kisiasa umeongezeka kwa kiasi kikubwa katika miongo miwili iliyopita.", "reference": "Women's participation in political leadership has increased significantly over the past two decades."},
        {"source": "Mpango wa fedha ndogo ndogo umesaidia maelfu ya wanawake kuanzisha biashara zao ndogo.", "reference": "The microfinance program has enabled thousands of women to start their own small businesses."},
        {"source": "Hali ya ukame imewalazimisha familia nyingi kuacha mashamba yao na kuhama kwenda maeneo ya mijini.", "reference": "Drought conditions have forced many families to abandon their farms and migrate to urban areas."},
        {"source": "Mmomonyoko wa pwani unaosababishwa na kupanda kwa kina cha bahari unawatishia jamii za wavuvi pwani.", "reference": "The coastal erosion caused by rising sea levels is threatening fishing communities along the shore."},
        {"source": "Dawa ya jadi inaendelea kucheza jukumu muhimu pamoja na huduma za afya za kisasa katika jamii nyingi.", "reference": "Traditional medicine continues to play an important role alongside modern healthcare in many communities."},
        {"source": "Dhamira ya kulinda amani imesaidia kurejesha utulivu katika eneo lililoathiriwa na migogoro.", "reference": "The peacekeeping mission has helped restore stability to the conflict-affected region."},
        {"source": "Uboreshaji wa upatikanaji wa huduma za afya ya uzazi umepunguza kwa kiasi kikubwa viwango vya vifo vya watoto wachanga na mama.", "reference": "Improved access to maternal healthcare has significantly reduced infant and maternal mortality rates."},
        {"source": "Mbuga za taifa huvutia maelfu ya watalii wa kimataifa kila mwaka, zikizalisha mapato muhimu.", "reference": "The national parks attract thousands of international tourists each year, generating vital revenue."},
        {"source": "Ukuaji wa haraka wa miji unaweka changamoto mpya kwa wapangaji wa miji na serikali za mtaa.", "reference": "Rapid urbanization is creating new challenges for city planners and local governments."},
        {"source": "Utangulizi wa huduma za benki za simu umebadilisha upatikanaji wa huduma za fedha katika jamii za vijijini.", "reference": "The introduction of mobile banking services has transformed financial access in rural communities."},
        {"source": "Vifaa bora vya usafi wa mazingira vinasaidia kuzuia kuenea kwa magonjwa yanayotokana na maji.", "reference": "Improved sanitation facilities are helping to prevent the spread of waterborne diseases."},
        {"source": "Kampeni ya kusoma na kuandika imesaidia mamilioni ya watu wazima kujifunza kusoma na kuandika.", "reference": "The literacy campaign has helped millions of adults learn to read and write."},
        {"source": "Wafanyakazi wa afya wa jamii ni muhimu katika kupanua huduma za afya kwa watu wasiohudumika.", "reference": "Community health workers are essential to extending healthcare services to underserved populations."},
        {"source": "Upanuzi wa muunganisho wa intaneti unafungua fursa mpya za kiuchumi kwa wajasiriamali vijana.", "reference": "The expansion of internet connectivity is opening new economic opportunities for young entrepreneurs."},
        {"source": "Mipango ya utalii endelevu inasaidia kulinda mifumo ikolojia ya asili huku ikisaidia uchumi wa mtaa.", "reference": "Sustainable tourism initiatives are helping protect natural ecosystems while supporting local economies."},
        {"source": "Ujenzi wa mifereji ya umwagiliaji umebadilisha ardhi kame kuwa maeneo yenye tija ya kilimo.", "reference": "The construction of irrigation canals has transformed arid land into productive agricultural zones."},
        {"source": "Makubaliano ya ushirikiano wa kikanda yanaimarisha uhusiano wa biashara na utamaduni kati ya mataifa jirani.", "reference": "Regional cooperation agreements are strengthening trade and cultural ties between neighboring nations."},
        {"source": "Ugunduzi wa akiba ya mafuta ya baharini una uwezo wa kubadilisha uchumi wa nchi.", "reference": "The discovery of offshore oil reserves has the potential to transform the country's economy."},
        {"source": "Juhudi za kupambana na usafirishaji haramu wa wanyamapori zinapata nguvu katika mkoa mzima.", "reference": "Efforts to combat illegal wildlife trafficking are gaining momentum across the region."},
        {"source": "Utangulizi wa huduma za serikali ya kielektroniki umefanya iwe rahisi kwa raia kupata utawala wa umma.", "reference": "The introduction of e-government services has made it easier for citizens to access public administration."},
        {"source": "Mbinu za kilimo zinazozingatia hali ya hewa zinawasaidia wakulima kukabiliana na mabadiliko ya hali ya hewa.", "reference": "Climate-smart agriculture techniques are helping farmers adapt to changing weather patterns."},
        {"source": "Daraja jipya juu ya mto litawezesha biashara na harakati kati ya maeneo mawili.", "reference": "The new bridge over the river will facilitate trade and movement between the two regions."},
        {"source": "Uwekezaji katika elimu ya awali ya utotoni unazalisha faida kubwa za kijamii na kiuchumi za muda mrefu.", "reference": "Investment in early childhood education produces significant long-term social and economic benefits."},
        {"source": "Mazungumzo ya amani yanalenga kutatua mgogoro wa eneo uliodumu kwa miongo mingi kati ya mataifa mawili.", "reference": "The peace talks aim to resolve the decades-long territorial dispute between the two nations."},
        {"source": "Fedha zinazotumwa na diaspora zinawakilisha chanzo kikubwa cha mapato kwa familia nyingi.", "reference": "Remittances from the diaspora represent a significant source of income for many families."},
        {"source": "Kuenea kwa simu mahiri kumebadilisha jinsi watu wanavyopata habari na taarifa.", "reference": "The proliferation of smartphones has transformed how people access news and information."},
        {"source": "Mipango ya kilimo cha mijini inasaidia kushughulikia changamoto za usalama wa chakula katika miji yenye watu wengi.", "reference": "Urban farming initiatives are helping address food security challenges in densely populated cities."},
        {"source": "Urejeshaji wa misitu ya mikoko pwani unasaidia kulinda dhidi ya mawimbi ya dhoruba.", "reference": "The restoration of mangrove forests along the coast is helping protect against storm surges."},
        {"source": "Mashirika ya msaada wa kimataifa yanafanya kazi kuboresha matokeo ya lishe kwa watoto wenye utapiamlo.", "reference": "International aid organizations are working to improve nutrition outcomes for malnourished children."},
        {"source": "Njia mpya ya reli itapunguza gharama za usafirishaji na kukuza biashara katika mkoa mzima.", "reference": "The new railway line will reduce transportation costs and boost trade across the region."},
        {"source": "Wajasiriamali wanawake wanaendesha ukuaji wa uchumi katika jamii nyingi zisizohudumika vizuri barani.", "reference": "Women entrepreneurs are driving economic growth in many underserved communities across the continent."},
        {"source": "Serikali imeahidi kuongeza uwekezaji katika mipango ya mafunzo ya ufundi ili kupunguza ukosefu wa ajira kwa vijana.", "reference": "The government has pledged to increase investment in vocational training programs to reduce youth unemployment."},
        {"source": "Desturi za kitamaduni zinahifadhiwa kupitia mipango ya urithi inayoongozwa na jamii.", "reference": "Traditional cultural practices are being preserved through community-led heritage programs."},
        {"source": "Maendeleo ya rasilimali za nishati ya jotoardhi yanaweza kutoa nguvu endelevu kwa mamilioni ya nyumba.", "reference": "The development of geothermal energy resources could provide sustainable power to millions of homes."},
        {"source": "Usalama wa mipaka umeimarishwa ili kuzuia usafirishaji haramu wa silaha na bidhaa haramu.", "reference": "Border security has been strengthened to prevent the smuggling of weapons and contraband."},
        {"source": "Ripoti ya kila mwaka inaonyesha maendeleo makubwa katika kupunguza viwango vya vifo vya watoto katika mkoa.", "reference": "The annual report shows significant progress in reducing child mortality rates across the region."},
        {"source": "Maendeleo katika teknolojia ya afya ya simu yanaleta huduma za uchunguzi kwa jamii za mbali.", "reference": "Advances in mobile health technology are bringing diagnostic services to remote communities."},
        {"source": "Uridhishaji wa makubaliano ya hali ya hewa unaashiria hatua muhimu katika ahadi za mazingira za nchi.", "reference": "The ratification of the climate agreement marks an important step in the country's environmental commitments."},
        {"source": "Mashirika yanayotegemea jamii yanacheza jukumu muhimu katika kusambaza msaada wa chakula kwa watu walio hatarini.", "reference": "Community-based organizations are playing a vital role in distributing food aid to vulnerable populations."},
        {"source": "Upanuzi wa bandari utaongeza uwezo wa nchi wa kushughulikia biashara ya kimataifa.", "reference": "The expansion of the port will increase the country's capacity to handle international trade."},
        {"source": "Juhudi za kukuza elimu ya wasichana zinaonyesha matokeo yanayoweza kupimika katika kufunga pengo la kijinsia.", "reference": "Efforts to promote girls' education are showing measurable results in closing the gender gap."},
        {"source": "Utangulizi wa mipango ya bima ya afya ya jamii umeboresha upatikanaji wa huduma za afya kwa watu wa vijijini.", "reference": "The introduction of community health insurance schemes has improved healthcare access for rural populations."},
        {"source": "Wanasayansi wanastudia athari za uchafuzi wa plastiki ndogo ndogo kwenye mifumo ikolojia ya baharini.", "reference": "Scientists are studying the impact of microplastic pollution on marine ecosystems."},
        {"source": "Mpango wa mafunzo ya ujuzi wa kidijitali umesaidia vijana maelfu kupata ajira katika sekta ya teknolojia.", "reference": "The digital skills training program has helped thousands of young people find employment in the technology sector."},
        {"source": "Benki za chakula za kikanda zinafanya kazi kushughulikia njaa na ukosefu wa usalama wa chakula miongoni mwa kaya zilizo hatarini.", "reference": "Regional food banks are working to address hunger and food insecurity among vulnerable households."},
        {"source": "Ujenzi wa vituo vipya vya afya katika maeneo yasiyohudumika vizuri utawaletea huduma za matibabu jamii karibu zaidi.", "reference": "The construction of new health centers in underserved areas will bring medical care closer to communities."},
        {"source": "Mifumo iliyoboreshwa ya utabiri wa hali ya hewa inawasaidia wakulima kupanga misimu yao ya kupanda na kuvuna.", "reference": "Improved weather forecasting systems are helping farmers plan their planting and harvesting seasons."},
        {"source": "Ugunduzi wa chanzo kipya cha maji chini ya ardhi unaweza kubadilisha upatikanaji wa maji kwa jamii zinazozunguka.", "reference": "The discovery of a new underground water source could transform water access for surrounding communities."},
        {"source": "Jumuiya ya kimataifa imeahidi msaada mkubwa wa fedha kwa juhudi za ujenzi upya.", "reference": "The international community has pledged significant financial support for the reconstruction effort."},
        {"source": "Wajasiriamali wa mtaa wanatumia majukwaa ya kidijitali kufikia wateja zaidi ya jamii zao za karibu.", "reference": "Local entrepreneurs are leveraging digital platforms to reach customers beyond their immediate communities."},
        {"source": "Hifadhi mpya ya asili itawalinda moja ya makazi ya mwisho yaliyobaki ya spishi ya nyani walio hatarini.", "reference": "The new nature reserve will protect one of the last remaining habitats of the endangered primate species."},
        {"source": "Uwekezaji ulioongezeka katika miundombinu ya nishati mbadala utapunguza utegemezi wa mafuta ya kisukuku yanayoagizwa kutoka nje.", "reference": "Increased investment in renewable energy infrastructure will reduce dependence on imported fossil fuels."},
        {"source": "Kituo cha redio cha jamii kinatangaza taarifa za afya na vidokezo vya kilimo kwa hadhira ya vijijini.", "reference": "The community radio station broadcasts health information and agricultural tips to rural audiences."},
        {"source": "Ushirikiano kati ya vyuo vikuu na sekta ya viwanda unazalisha wahitimu wenye ujuzi unaohusiana na uchumi wa kisasa.", "reference": "Partnerships between universities and industry are producing graduates with skills relevant to the modern economy."},
        {"source": "Uhamiaji wa kila mwaka wa nyumbu katika tambarare huvutia watalii kutoka kote duniani.", "reference": "The annual migration of wildebeest across the plains attracts tourists from around the world."},
        {"source": "Serikali imewekeza katika kuboresha barabara ili kuunganisha jamii za wakulima wa vijijini na masoko ya mijini.", "reference": "The government has invested in upgrading roads to connect rural farming communities to urban markets."},
        {"source": "Upatikanaji wa haki bado ni mdogo kwa raia wengi wa kipato kidogo kutokana na gharama kubwa za kisheria.", "reference": "Access to justice remains limited for many low-income citizens due to high legal costs."},
        {"source": "Juhudi za kuboresha ubora wa hewa katika miji mikubwa zinaendelezwa na kanuni mpya za mazingira.", "reference": "Efforts to improve air quality in major cities are being driven by new environmental regulations."},
        {"source": "Kiwanda kipya cha matibabu ya maji kitatoa maji safi ya kunywa kwa wakazi zaidi ya nusu milioni.", "reference": "The new water treatment plant will provide clean drinking water to more than half a million residents."},
        {"source": "Mipango ya uongozi wa vijana inaweza nguvu kizazi kijacho kushiriki katika maisha ya kiraia na kisiasa.", "reference": "Youth leadership programs are empowering the next generation to participate in civic and political life."},
    ],
}

@router.post("/run-benchmark")
async def run_wmt_benchmark(request: WMTRequestCreate):
    """Run WMT benchmark test"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        language_pair = request.language_pair.lower()

        if language_pair not in WMT_SAMPLE_DATA:
            raise HTTPException(
                status_code=400,
                detail=f"Language pair {language_pair} not supported. Available: {list(WMT_SAMPLE_DATA.keys())}"
            )

        sample_data = WMT_SAMPLE_DATA[language_pair]
        selected_samples = random.sample(sample_data, min(request.sample_size, len(sample_data)))

        source_lang, target_lang = language_pair.split('-')
        model_to_use = get_model_for_language_pair(source_lang, target_lang)

        results = []

        for sample in selected_samples:
            try:
                mt_translation = translation_service.translate_by_model_type(
                    sample["source"], model_to_use,
                    source_lang=source_lang, target_lang=target_lang
                )
                # BLEU: sacrebleu returns 0–100, store as-is
                bleu_score = sacrebleu.sentence_bleu(mt_translation, [sample["reference"]]).score
                results.append(WMTBenchmarkResult(
                    source_text=sample["source"],
                    reference_text=sample["reference"],
                    mt_translation=mt_translation,
                    bleu_score=bleu_score,
                    language_pair=language_pair
                ))
            except Exception as e:
                logger.error(f"Translation failed for sample: {e}")
                results.append(WMTBenchmarkResult(
                    source_text=sample["source"],
                    reference_text=sample["reference"],
                    mt_translation=f"Translation failed: {str(e)}",
                    bleu_score=0.0,
                    language_pair=language_pair
                ))

        hypotheses = [r.mt_translation for r in results]
        references = [r.reference_text for r in results]
        avg_bleu = sacrebleu.corpus_bleu(hypotheses, [references]).score if results else 0.0  # 0–100

        benchmark_record = await prisma.wmtbenchmark.create(
            data={
                "languagePair": language_pair,
                "sampleSize": len(results),
                "averageBleuScore": avg_bleu,
                "modelUsed": model_to_use,
                "results": [r.dict() for r in results]
            }
        )

        return {
            "benchmark_id": benchmark_record.id,
            "language_pair": language_pair,
            "sample_size": len(results),
            "average_bleu_score": avg_bleu,
            "model_used": model_to_use,
            "results": results
        }

    except Exception as e:
        logger.error(f"WMT benchmark failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/benchmarks")
async def get_benchmark_history():
    try:
        if not prisma.is_connected():
            await prisma.connect()
        benchmarks = await prisma.wmtbenchmark.find_many(order={"createdAt": "desc"}, take=50)
        return {"benchmarks": benchmarks, "total": len(benchmarks)}
    except Exception as e:
        logger.error(f"Failed to get benchmarks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/benchmarks/{benchmark_id}")
async def get_benchmark_details(benchmark_id: str):
    try:
        if not prisma.is_connected():
            await prisma.connect()
        benchmark = await prisma.wmtbenchmark.find_unique(where={"id": benchmark_id})
        if not benchmark:
            raise HTTPException(status_code=404, detail="Benchmark not found")
        return benchmark
    except Exception as e:
        logger.error(f"Failed to get benchmark details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-request")
async def create_wmt_benchmark_request(
    language_pair: str = Query(...),
    sample_size: int = Query(100),
    multi_engine_service=Depends(get_multi_engine_service),
):
    """Create a WMT benchmark translation request"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        from prisma.enums import MTModel
        from prisma import Json

        normalized_lp = normalize_lang_pair(language_pair)

        model_mapping_enum = {
            'jpn-eng': MTModel.ELAN_MT_JP_EN,   'jp-en': MTModel.ELAN_MT_JP_EN,
            'eng-jpn': MTModel.MARIAN_MT_EN_JP, 'en-jp': MTModel.MARIAN_MT_EN_JP,
            'eng-fra': MTModel.MARIAN_MT_EN_FR, 'en-fr': MTModel.MARIAN_MT_EN_FR,
            'fra-eng': MTModel.MARIAN_MT_FR_EN, 'fr-en': MTModel.MARIAN_MT_FR_EN,
            'jpn-fra': MTModel.PIVOT_JP_EN_FR,  'jp-fr': MTModel.PIVOT_JP_EN_FR,
            'eng-swh': MTModel.NLLB_MULTILINGUAL, 'en-sw': MTModel.NLLB_MULTILINGUAL,
            'swh-eng': MTModel.NLLB_MULTILINGUAL, 'sw-en': MTModel.NLLB_MULTILINGUAL,
        }

        mt_model_enum_val = model_mapping_enum.get(language_pair, model_mapping_enum.get(normalized_lp, MTModel.MARIAN_MT_EN_FR))

        source_lang, target_lang = normalized_lp.split('-')
        source_lang_code = source_lang.upper()
        target_lang_code = target_lang.upper()

        wmt_request = await prisma.translationrequest.create(
            data={
                "sourceLanguage": source_lang_code,
                "targetLanguages": [target_lang_code],
                "languagePair": normalized_lp,
                "wordCount": sample_size * 20,
                "fileName": f"wmt_benchmark_{language_pair}_{sample_size}.txt",
                "mtModel": mt_model_enum_val,
                "status": "IN_PROGRESS",
                "requestType": "WMT_BENCHMARK"
            }
        )

        lp_key = f"{source_lang}-{target_lang}"
        wmt_samples = WMT_SAMPLE_DATA.get(lp_key, [])
        if not wmt_samples:
            raise HTTPException(
                status_code=400,
                detail=f"No WMT sample data for language pair {lp_key}. Available: {list(WMT_SAMPLE_DATA.keys())}"
            )

        selected_samples = wmt_samples[:sample_size]

        for i, sample in enumerate(selected_samples):
            source_text = sample["source"]
            reference_text = sample["reference"]
            try:
                model_key_for_wmt = get_model_for_language_pair(source_lang, target_lang)
                translated_text = ""

                if model_key_for_wmt == 'PIVOT_ELAN_HELSINKI':
                    translated_text = await multi_engine_service._translate_with_pivot(
                        source_text.strip(), source_lang_code, target_lang_code,
                        multi_engine_service.engine_configs['elan_quality']['pivot_strategy']
                    )
                else:
                    prefix_or_lang_tag = None
                    model_info_from_ts = next(
                        (info for info in translation_service.language_pair_models.get(f"{source_lang.upper()}-{target_lang.upper()}", [])
                         if info[0] == model_key_for_wmt),
                        None
                    )
                    if model_info_from_ts and len(model_info_from_ts) == 3:
                        prefix_or_lang_tag = model_info_from_ts[2]

                    translated_text = translation_service.translate_by_model_type(
                        source_text.strip(), model_key_for_wmt,
                        source_lang=source_lang.lower(), target_lang=target_lang.lower(),
                        target_lang_tag=prefix_or_lang_tag
                    )

                if target_lang_code == 'JP':
                    translated_text = detokenize_japanese(translated_text)

                await prisma.translationstring.create(
                    data={
                        "sourceText": source_text, "translatedText": translated_text,
                        "referenceText": reference_text, "referenceType": "WMT",
                        "hasReference": True, "targetLanguage": target_lang_code,
                        "status": "REVIEWED", "isApproved": False, "processingTimeMs": 1000,
                        "translationRequestId": wmt_request.id, "fuzzyMatches": Json("[]"),
                    }
                )

            except Exception as e:
                logger.error(f"Failed to translate WMT sample {i}: {e}")
                await prisma.translationstring.create(
                    data={
                        "sourceText": source_text, "translatedText": f"Translation failed: {str(e)}",
                        "referenceText": reference_text, "referenceType": "WMT",
                        "hasReference": True, "targetLanguage": target_lang_code,
                        "status": "DRAFT", "isApproved": False, "processingTimeMs": 0,
                        "translationRequestId": wmt_request.id, "fuzzyMatches": Json("[]"),
                    }
                )

        await prisma.translationrequest.update(where={"id": wmt_request.id}, data={"status": "COMPLETED"})

        return {
            "success": True, "request_id": wmt_request.id,
            "language_pair": language_pair, "sample_size": sample_size,
            "message": f"WMT benchmark request created for {language_pair}"
        }

    except Exception as e:
        logger.error(f"Failed to create WMT request: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create WMT benchmark request: {str(e)}")

@router.get("/requests")
async def get_wmt_requests():
    try:
        if not prisma.is_connected():
            await prisma.connect()
        wmt_requests = await prisma.translationrequest.find_many(
            where={"requestType": "WMT_BENCHMARK"},
            include={"translationStrings": True, "qualityMetrics": True}
        )
        wmt_requests.sort(key=lambda x: x.createdAt, reverse=True)
        return wmt_requests
    except Exception as e:
        logger.error(f"Failed to fetch WMT requests: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch WMT requests: {str(e)}")

@router.get("/results/{request_id}")
async def get_wmt_results(request_id: str):
    try:
        if not prisma.is_connected():
            await prisma.connect()
        wmt_request = await prisma.translationrequest.find_unique(
            where={"id": request_id},
            include={"translationStrings": True, "qualityMetrics": True}
        )
        if not wmt_request:
            raise HTTPException(status_code=404, detail="WMT request not found")
        return wmt_request
    except Exception as e:
        logger.error(f"Failed to fetch WMT results: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch WMT results: {str(e)}")


@router.post("/ingest-to-tm/{request_id}")
async def ingest_wmt_to_tm(request_id: str):
    """Ingest WMT reference translations into Translation Memory."""
    if not prisma.is_connected():
        await prisma.connect()

    wmt_request = await prisma.translationrequest.find_unique(
        where={"id": request_id}, include={"translationStrings": True},
    )
    if not wmt_request:
        raise HTTPException(status_code=404, detail="WMT request not found")

    source_lang = str(wmt_request.sourceLanguage)
    ingested = 0
    skipped = 0

    for ts in wmt_request.translationStrings:
        if not ts.referenceText or ts.referenceType != "WMT":
            skipped += 1
            continue
        existing = await prisma.translationmemory.find_first(
            where={"sourceText": ts.sourceText, "targetLanguage": ts.targetLanguage, "sourceLanguage": source_lang}
        )
        if existing:
            skipped += 1
            continue
        await prisma.translationmemory.create(
            data={
                "sourceText": ts.sourceText, "targetText": ts.referenceText,
                "sourceLanguage": source_lang, "targetLanguage": ts.targetLanguage,
                "quality": "HIGH", "domain": "wmt_benchmark", "originalRequestId": request_id,
            }
        )
        ingested += 1

    return {
        "success": True, "ingested": ingested, "skipped": skipped,
        "message": f"Ingested {ingested} WMT reference translations into TM (skipped {skipped} duplicates/ineligible)",
    }


# ---------------------------------------------------------------------------
# Multi-engine controlled benchmark
# ---------------------------------------------------------------------------

# Maps internal data/DB language codes to ISO codes expected by the engine service.
# "jp" is the internal key (WMT_SAMPLE_DATA keys, DB writes);
# the engine service uses "ja" (ISO 639-1) in all its supported_pairs configs.
_INTERNAL_TO_ISO = {"jp": "ja"}

_SOURCE_LANG_ENUM = {"en": "EN", "fr": "FR", "jp": "JP", "ja": "JP", "sw": "SW"}

@router.post("/run-multi-engine")
async def run_multi_engine_benchmark(
    language_pair: str = Query(..., description="Canonical pair, e.g. en-fr, jp-en, en-sw"),
    engines: Optional[List[str]] = Query(None, description="Engine IDs to run. Defaults to all available."),
    notes: Optional[str] = Query(None, description="Label stored on EvalSnapshot rows, e.g. 'baseline'"),
    multi_engine_service=Depends(get_multi_engine_service),
    comet_model=Depends(get_comet_model),
):
    """Run every available MT engine on the same WMT/FLORES reference sentences.

    Unified metric storage conventions:
      bleuScore / chrfScore / avgBleu / avgChrf:  0–100  (raw sacrebleu — NOT divided by 100)
      terScore  / avgTer:                         0–100  (capped at 100)
      cometScore / avgComet:                      0–1    (raw COMET model output — NOT multiplied by 100)
    """
    if not prisma.is_connected():
        await prisma.connect()

    normalized_lp = normalize_lang_pair(language_pair)
    source_lang, target_lang = normalized_lp.split("-")

    lp_key = f"{source_lang}-{target_lang}"
    samples = WMT_SAMPLE_DATA.get(lp_key)
    if not samples:
        raise HTTPException(
            status_code=400,
            detail=f"No sample data for '{lp_key}'. Available: {list(WMT_SAMPLE_DATA.keys())}",
        )

    source_lang_enum = _SOURCE_LANG_ENUM.get(source_lang)
    if not source_lang_enum:
        raise HTTPException(status_code=400, detail=f"Unsupported source language: {source_lang}")

    # ISO codes for the engine service (jp → ja)
    service_source = _INTERNAL_TO_ISO.get(source_lang, source_lang)
    service_target = _INTERNAL_TO_ISO.get(target_lang, target_lang)

    available = multi_engine_service.get_available_engines_for_pair(
        service_source.upper(), service_target.upper()
    )
    engines_to_run = [e for e in (engines or available) if e in available]
    if not engines_to_run:
        raise HTTPException(
            status_code=400,
            detail=f"No engines available for '{lp_key}'. Available: {available}",
        )

    logger.info(
        f"Multi-engine benchmark: {lp_key}, {len(samples)} sentences, "
        f"engines={engines_to_run}, comet={'yes' if comet_model else 'no'}"
    )

    wmt_request = await prisma.translationrequest.create(
        data={
            "sourceLanguage": source_lang_enum,
            "targetLanguages": [target_lang.upper()],
            "languagePair": normalized_lp,
            "wordCount": len(samples) * 15,
            "fileName": f"wmt_benchmark_{lp_key}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt",
            "mtModel": "MULTI_ENGINE",
            "status": "IN_PROGRESS",
            "requestType": "WMT_BENCHMARK",
        }
    )
    request_id = wmt_request.id

    engine_results: Dict[str, Dict] = {}

    for engine_id in engines_to_run:
        logger.info(f"  Running engine: {engine_id}")
        hyps: List[str] = []
        refs: List[str] = []
        string_ids: List[str] = []

        for sample in samples:
            if engine_id == 'gemini_transcreation' and len(hyps) >= 50:
                break
            src = sample["source"]
            ref = sample["reference"]
            try:
                # Use ISO codes so the engine service finds the correct model mapping
                result = await multi_engine_service.translate_with_engine(
                    src, service_source.upper(), service_target.upper(), engine_id
                )
                translation = result.get("text", "")
                if target_lang == "jp":
                    translation = detokenize_japanese(translation)
            except Exception as exc:
                logger.warning(f"    {engine_id} failed on segment: {exc}")
                translation = ""

            hyps.append(translation)
            refs.append(ref)

            # DB writes keep internal codes (e.g. "JP"), not ISO
            ts = await prisma.translationstring.create(
                data={
                    "sourceText": src, "translatedText": translation,
                    "referenceText": ref, "referenceType": "WMT",
                    "hasReference": True, "targetLanguage": target_lang.upper(),
                    "status": "REVIEWED", "isApproved": True,
                    "selectedEngine": engine_id, "processingTimeMs": 0,
                    "translationRequestId": request_id, "fuzzyMatches": Json("[]"),
                }
            )
            string_ids.append(ts.id)

        valid = [(h, r) for h, r in zip(hyps, refs) if h]
        if not valid:
            engine_results[engine_id] = {"error": "all segments failed", "string_ids": string_ids}
            continue

        valid_hyps, valid_refs = zip(*valid)
        valid_hyps, valid_refs = list(valid_hyps), list(valid_refs)

        # Corpus metrics — all returned at natural sacrebleu scale
        is_cjk = target_lang in ("jp", "ja")
        bleu = sacrebleu.corpus_bleu(valid_hyps, [valid_refs], tokenize="char" if is_cjk else "13a").score
        chrf = sacrebleu.corpus_chrf(valid_hyps, [valid_refs]).score
        if is_cjk:
            cjk_hyps = [' '.join(list(h)) for h in valid_hyps]
            cjk_refs = [' '.join(list(r)) for r in valid_refs]
            ter = min(100.0, sacrebleu.corpus_ter(cjk_hyps, [cjk_refs]).score)
        else:
            ter = min(100.0, sacrebleu.corpus_ter(valid_hyps, [valid_refs]).score)

        # COMET — raw 0–1
        comet_avg: Optional[float] = None
        comet_per_seg: List[Optional[float]] = [None] * len(hyps)
        if comet_model and valid_hyps:
            try:
                comet_samples = [
                    {"src": s["source"], "mt": h, "ref": r}
                    for s, h, r in zip(samples, hyps, refs) if h
                ]
                scores = comet_predict(comet_model, comet_samples)
                comet_avg = round(statistics.mean(scores), 4)
                valid_idx = [i for i, h in enumerate(hyps) if h]
                for i, score in zip(valid_idx, scores):
                    comet_per_seg[i] = round(score, 4)
            except Exception as exc:
                logger.warning(f"    COMET failed for {engine_id}: {exc}")

        # Per-segment QualityMetrics rows
        for i, (ts_id, hyp, ref) in enumerate(zip(string_ids, hyps, refs)):
            if not hyp:
                continue
            seg_bleu = sacrebleu.sentence_bleu(hyp, [ref]).score               # 0–100
            seg_chrf = sacrebleu.sentence_chrf(hyp, [ref]).score               # 0–100
            seg_ter  = min(100.0, sacrebleu.corpus_ter([hyp], [[ref]]).score)  # 0–100

            await prisma.qualitymetrics.create(
                data={
                    "translationStringId": ts_id,
                    "translationRequestId": request_id,
                    "engineName": engine_id,
                    "bleuScore": round(seg_bleu, 4),  # 0–100
                    "chrfScore": round(seg_chrf, 4),  # 0–100
                    "terScore":  round(seg_ter,  4),  # 0–100
                    "cometScore": comet_per_seg[i],   # 0–1
                    "hasReference": True,
                    "referenceType": "WMT",
                }
            )

        snap = await prisma.evalsnapshot.create(
            data={
                "requestId": request_id,
                "languagePair": normalized_lp,
                "engineName": engine_id,
                "avgBleu":  round(bleu, 4),   # 0–100
                "avgChrf":  round(chrf, 4),   # 0–100
                "avgTer":   round(ter,  4),   # 0–100
                "avgComet": comet_avg,         # 0–1
                "segmentCount": len(valid_hyps),
                "notes": notes,
            }
        )

        engine_results[engine_id] = {
            "engine": engine_id,
            "bleu":  round(bleu, 1),
            "chrf":  round(chrf, 1),
            "ter":   round(ter,  1),
            "comet": round(comet_avg, 3) if comet_avg is not None else None,
            "n_segments": len(valid_hyps),
            "snapshot_id": snap.id,
            "error": None,
        }
        logger.info(
            f"    {engine_id}: BLEU={bleu:.1f} ChrF={chrf:.1f} TER={ter:.1f}"
            + (f" COMET={comet_avg:.3f}" if comet_avg else "")
        )

    await prisma.translationrequest.update(
        where={"id": request_id}, data={"status": "COMPLETED"},
    )

    comparison = sorted(
        [v for v in engine_results.values() if isinstance(v, dict) and "engine" in v],
        key=lambda r: (r["comet"] or 0, r["bleu"]),
        reverse=True,
    )

    return {
        "success": True,
        "language_pair": normalized_lp,
        "request_id": request_id,
        "n_sentences": len(samples),
        "engines_run": len(comparison),
        "comet_available": comet_model is not None,
        "notes": notes,
        "comparison": comparison,
    }


@router.post("/recompute-snapshots")
async def recompute_snapshots(
    language_pair: Optional[str] = Query(None, description="Limit to one pair, e.g. en-fr. Omit for all pairs."),
    notes: Optional[str] = Query(None, description="Label for new snapshots, e.g. 'baseline'"),
    comet_model=Depends(get_comet_model),
):
    """Recompute EvalSnapshots from existing WMT translation strings without re-translating.

    Deletes existing snapshots for the affected (engine, language_pair) combinations,
    then recomputes corpus BLEU / ChrF / TER / COMET from the stored MT outputs and
    WMT reference texts.  Use this after a metric bug fix to avoid re-running translations.
    """
    if not prisma.is_connected():
        await prisma.connect()

    # Fetch all WMT translation strings that have a referenceText
    where: dict = {"referenceType": "WMT", "referenceText": {"not": None}}
    if language_pair:
        normalized_lp = normalize_lang_pair(language_pair)
        src, tgt = normalized_lp.split("-")
        where["translationRequest"] = {
            "is": {
                "sourceLanguage": src.upper(),
                "targetLanguages": {"has": tgt.upper()},
            }
        }

    strings = await prisma.translationstring.find_many(
        where=where,
        include={"translationRequest": True},
    )

    if not strings:
        return {"success": True, "message": "No WMT strings found matching criteria.", "snapshots_created": 0}

    # Group by (language_pair, engine_name, request_id)
    from collections import defaultdict
    groups: dict = defaultdict(list)
    for s in strings:
        if not s.translationRequest:
            continue
        src_lang = normalize_lang_pair(
            f"{s.translationRequest.sourceLanguage}-{s.targetLanguage}"
        ).split("-")[0]
        tgt_lang = normalize_lang_pair(
            f"{s.translationRequest.sourceLanguage}-{s.targetLanguage}"
        ).split("-")[1]
        lp = f"{src_lang}-{tgt_lang}"
        engine = getattr(s, "engineName", None) or s.selectedEngine or "unknown"
        req_id = s.translationRequestId
        groups[(lp, engine, req_id)].append(s)

    created_snapshots = []
    for (lp, engine_id, req_id), segs in groups.items():
        hyps = [s.translatedText or "" for s in segs]
        refs = [s.referenceText or "" for s in segs]

        valid = [(h, r) for h, r in zip(hyps, refs) if h and r]
        if not valid:
            continue
        valid_hyps, valid_refs = zip(*valid)
        valid_hyps, valid_refs = list(valid_hyps), list(valid_refs)

        tgt = lp.split("-")[1]
        is_cjk = tgt in ("jp", "ja")

        try:
            bleu = sacrebleu.corpus_bleu(valid_hyps, [valid_refs], tokenize="char" if is_cjk else "13a").score
            chrf = sacrebleu.corpus_chrf(valid_hyps, [valid_refs]).score
            if is_cjk:
                cjk_hyps = [" ".join(list(h)) for h in valid_hyps]
                cjk_refs = [" ".join(list(r)) for r in valid_refs]
                ter = min(100.0, sacrebleu.corpus_ter(cjk_hyps, [cjk_refs]).score)
            else:
                ter = min(100.0, sacrebleu.corpus_ter(valid_hyps, [valid_refs]).score)
        except Exception as e:
            logger.warning(f"Metric computation failed for ({lp}, {engine_id}): {e}")
            continue

        comet_avg: Optional[float] = None
        if comet_model:
            try:
                src_lang = lp.split("-")[0]
                comet_samples = [
                    {"src": s.sourceText, "mt": h, "ref": r}
                    for s, h, r in zip(segs, hyps, refs) if h and r
                ]
                scores = comet_predict(comet_model, comet_samples)
                comet_avg = round(statistics.mean(scores), 4)
            except Exception as e:
                logger.warning(f"COMET failed for ({lp}, {engine_id}): {e}")

        # Delete stale snapshot for this (engine, pair, request)
        await prisma.evalsnapshot.delete_many(
            where={"engineName": engine_id, "languagePair": lp, "requestId": req_id}
        )

        snap = await prisma.evalsnapshot.create(
            data={
                "requestId": req_id,
                "languagePair": lp,
                "engineName": engine_id,
                "avgBleu": round(bleu, 4),
                "avgChrf": round(chrf, 4),
                "avgTer": round(ter, 4),
                "avgComet": comet_avg,
                "segmentCount": len(valid_hyps),
                "notes": notes or "recomputed",
            }
        )
        created_snapshots.append({
            "language_pair": lp,
            "engine": engine_id,
            "bleu": round(bleu, 1),
            "chrf": round(chrf, 1),
            "ter": round(ter, 1),
            "comet": round(comet_avg, 3) if comet_avg else None,
            "n": len(valid_hyps),
            "snapshot_id": snap.id,
        })
        logger.info(f"Recomputed snapshot ({lp}, {engine_id}): BLEU={bleu:.1f} ChrF={chrf:.1f} TER={ter:.1f}")

    return {
        "success": True,
        "snapshots_created": len(created_snapshots),
        "snapshots": sorted(created_snapshots, key=lambda x: (x["language_pair"], x["engine"])),
    }
