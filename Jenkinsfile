// Jenkinsfile — Validación automática del Sistema de Inventario
// Tecnológico (Práctica 12, Servidores II).
// Cinco etapas, iguales para todos los equipos. Jenkins lo lee desde
// el repositorio de GitHub (Pipeline script from SCM, rama */main).
pipeline {
    agent any

    stages {
        stage('Archivos del proyecto') {
            steps {
                sh 'test -f compose.yaml'
                sh 'test -f db/init.sql'
                sh 'test -f nginx/default.conf'
                sh 'test -f .env.ejemplo'
            }
        }

        stage('Credenciales protegidas') {
            steps {
                sh 'grep -qx ".env" .gitignore'
                sh 'test ! -f .env'
            }
        }

        stage('Estructura de Compose') {
            steps {
                sh 'grep -q "^  nginx:" compose.yaml'
                sh 'grep -q "^  app:" compose.yaml'
                sh 'grep -q "^  db:" compose.yaml'
                sh 'grep -q "healthcheck:" compose.yaml'
                sh 'grep -q "image: .*/inventario-app:1.0" compose.yaml'
            }
        }

        stage('Historial en Git') {
            steps {
                sh 'git log --oneline -5'
            }
        }

        stage('Sistema disponible') {
            steps {
                sh 'curl -fsS http://nginx/salud'
            }
        }
    }
}
