# OrgMind — Code Map

## app/main.py

Point d'entrée FastAPI. Crée les tables SQLAlchemy au démarrage, monte 3 routers (auth, documents, query), expose / et /health.

## app/config.py

Charge les settings depuis .env (GROQ_API_KEY, CHROMA_DB_PATH, JWT_SECRET, etc.).

## app/database.py

Cree notre connextion avec la database (postgres ) configurations neccessaire pour run ma Database ( engine , session et dependence)

## app/models.py

Dans ces dossiers nous avons 4 classes de sqlachemy qui est notre ORM qui cree 4 tables dans notre base de donnee

Organisation : C'est une class qui Cree une table dans ma database appelle organization qui enregistre toute les organisations dans mon appication avec leurs id , nom , sectuer , et la date de creation
Et tout organisation a des users des documents et des historique des conversatation des users

User : C'est une class qui cree une table users dans la base de donnee , avec id , email , password , full_name , role , is_active , created , organisation_id et tout users a une relation avec sa conversation

Document : c'est une class qui cree une table documents dans la base de donne et chaque document a un id , filename, original_name , file_type , source , status , chunk_count, uploaded_at et l'organisation_id

Conversation : C'est une class qui cree une table conversation dans la base de donnee ,avec un id, question , answer , source , created_at , user_id , organisation_id

## app/services/auth_service.py

Ici c'est toute la logique de l'authenticification

1.  hash_password : Function qui prend un string et lui encode
2.  verify_password : il verifie le password que le user a saisi en plain et celui qui est hash ,le deux utilise le meme encodeur
3.  create_token : cree une token pour les users qui sont connecte avec JWT_ALgorithm
4.  verify_token : verifie que le token est toujours active ou valide
5.  get_current_user : prend tout ce qui appartient au user connected , son token , user_id

## app/services/rag_service.py

Ce ficher a toute notre logique Rag separee en 3 functions

1. ingest document : c'est une function Qui load le pdf en pages , split pages en 500 caracters par chunks et une duplication de 50 caracters , ajoute le metadata sur chaque chunks(org_id , doc_id , filemname ) , sauvegarde les chunk en chromad en leurs nom de collection et return la taille des chunks
2. retrieve_document : c'est une fonction qui prend ka question , l'oganisation_id , et jusqu'a combien des chunk peut etre retrieved , Cherche la similarity des chunk d'apres la question et return la liste des chunks qui sont relevants d'apres la question
3. query_documents : c'est une function qui prensd la question et 'organisation id en parametre , retrived la list des chunks et le garder dans results , Prendre tout les contenu des chunks qu on a retrieved , le mettre en semble dans une variable context , on prend tout les metadata(filemname) des chunks retrieved on le met dans sources , on prend tout les metadata(doc_ids) des chunks retrievd dans doc-ids
   Note de securite : query documents retrieved sur toute la collection sans filtrer par doc_id. un user de l'org_q peut donc voir tous les documents de l'org1

4. creer le prompt , generez la reponse avec llm et returner la question , sources , doc_ids , context

## app/routes/auth.py

C'est mon endpoint qui permet aux users de creer des comptes d'organisation et Login

1. register_org : Check email si ca Existe deja , sinon Creer une organisation avec son premier user admin
2. login : permet au user de log in si le compte existe dans la database
3. get_met : return le user qui est connecter avec tout ses informations en un coup

## app/routes/documents.py

c'est le Endpoint qui permet d upload un document pdf , verifier son type , save le document dans postgres , aussi la taille des chunk de chromadb ,
get_document: permet de retrouver tout les document d'une organisation
delete_document : permet d'effcer un document

## app/routes/query.py

c'est le endpoint qui permet de query un document , save une conversation , returner une reponse
ask_question : prend la reponse dans le ficher rag avec la function query_documents , save the conversatation dans notre basse de donnee , return la reponse avec la source
get_history : qui retrouver toute la conversatation du user le return comme un dictionnaire

## app/evaluation.py

Evaluation est un script qui permet d'evaluer la reponse de mon rag , avec des question test et ses reponses , je calcul la precision pour savoir le chunk que je retrieved contien de relevant chunks , aussi de s'avoir si les LLM est faithful au contenu des chunks qu il recois

## app/check_pdf_extraction.py

c'est un script d'experimentation des deux methode "Dense " et "BM25" afin de voir si le quqel perform mieux ;'un check la similarity des mots et d'autre travail avec le mot a mot
