# Week 12: Homework 1: Project: Facial Recognition on Raspberry Pi with AWS Rekognition
In this exercise we are going to detect face from live feed of Raspberry Pi. But as we are using Raspbian OS in VirtualBox, we don’t using Pi Camera. So, we need to use our webcam from host OS. So, we need such solution that will work in both like VirtualBox environment and in real hardware i.e. Pi Camera. For VirtualBox environment we have other challenge like we need to attach host OS with guest OS.
To achieve our goal we are going to use following technology -
1. Python: Make the entire project happen
2. OpenCV: Handle camera stream
3. boto3: Communicate with AWS

Here we are using OpenCV due to portability of project. Like when we use real hardware we don’t need to change our code much. Also OpenCV is a very powerful project, we can add many feature in our project with the help of OpenCV.
Here is the steps we are going to follow to achieve our goal -
1. Prepare OS to attach host camera
2. Install required module into Raspbian OS
3. Configure AWS
4. Code our project
5. Execute and test
