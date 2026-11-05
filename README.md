# Language-Detection
A lot of the base ideas and architecture came from this github repo:
https://github.com/githubharald/SimpleHTR
The first part of the architecture is very similar, both using several convolution layers to obtain a
"features list" which was a series of features collected at different time stamps.
Instead of using an LSTM like he did, however, we decided to mimic a rnn by creating
a single dimensional convolution layer looking at a sliding window of features to make predictions
at different timesteps without information from other parts of the image.
We used a total of four data sets: One was a collection of handwriting from the IAM database
one was a collection of german handwriting from historical documents, and lastly
we generated english and german datasets from text labels from the original datasets
into png format in Courier font.
